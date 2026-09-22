"""MySQL MCP Server - Business Analytical Tools.

Exposes strictly pre-approved business-level analytical functions.
Arbitrary SQL execution is strictly prohibited.
Enforces parameter validation, query timeouts, row limits, and structured JSON output.
"""

import time
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from backend.config import settings
from backend.mysql import mysql_manager
from backend.models.schemas import MCPToolResult

logger = logging.getLogger("enterprise_analyst.mcp.mysql")

VALID_STATUSES = {"Completed", "Pending", "Cancelled", "Returned"}
VALID_SEGMENTS = {"Enterprise", "Mid-Market", "SMB"}


def _serialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Converts Decimal, Date, and other non-JSON types into standard JSON primitives."""
    clean = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            clean[k] = float(v)
        elif hasattr(v, "isoformat"):
            clean[k] = v.isoformat()
        else:
            clean[k] = v
    return clean


class MySQLMCPServer:
    """Enterprise MySQL Model Context Protocol Tool Provider."""

    def __init__(self):
        self.mysql = mysql_manager

    def get_revenue_by_region(
        self,
        status: str = "Completed",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> MCPToolResult:
        """Retrieves aggregated revenue grouped by geographical region."""
        start_time = time.time()
        if status not in VALID_STATUSES:
            return MCPToolResult(source="mysql", error=f"Invalid status '{status}'. Allowed: {VALID_STATUSES}")

        query = """
            SELECT 
                region_name,
                ROUND(SUM(revenue), 2) AS total_revenue,
                COUNT(DISTINCT order_id) AS order_count,
                COUNT(DISTINCT customer_id) AS customer_count
            FROM order_revenue
            WHERE order_status = %s
        """
        params: List[Any] = [status]

        if start_date:
            query += " AND order_date >= %s"
            params.append(start_date)
        if end_date:
            query += " AND order_date <= %s"
            params.append(end_date)

        query += " GROUP BY region_name ORDER BY total_revenue DESC;"

        try:
            raw_data = self.mysql.execute_query(query, tuple(params))
            data = [_serialize_row(r) for r in raw_data]
            duration = round((time.time() - start_time) * 1000, 2)
            return MCPToolResult(
                source="mysql",
                metric="revenue_by_region",
                data=data,
                row_count=len(data),
                execution_time_ms=duration,
            )
        except Exception as e:
            logger.error("get_revenue_by_region error: %s", e)
            return MCPToolResult(source="mysql", metric="revenue_by_region", error=str(e))

    def get_monthly_revenue(
        self,
        months: int = 6,
        status: str = "Completed",
    ) -> MCPToolResult:
        """Retrieves monthly revenue timeline for trend analysis."""
        start_time = time.time()
        if status not in VALID_STATUSES:
            return MCPToolResult(source="mysql", error=f"Invalid status '{status}'.")
        months = max(1, min(months, 36))

        # Uses substr(order_date, 1, 7) which works on both MySQL and SQLite fallback
        query = """
            SELECT 
                SUBSTR(order_date, 1, 7) AS month,
                ROUND(SUM(revenue), 2) AS monthly_revenue,
                COUNT(DISTINCT order_id) AS total_orders
            FROM order_revenue
            WHERE order_status = %s
            GROUP BY SUBSTR(order_date, 1, 7)
            ORDER BY month DESC
            LIMIT %s;
        """
        try:
            raw_data = self.mysql.execute_query(query, (status, months))
            # Sort ascending chronologically for clean chart display
            raw_data = sorted(raw_data, key=lambda x: x["month"])
            data = [_serialize_row(r) for r in raw_data]
            duration = round((time.time() - start_time) * 1000, 2)
            return MCPToolResult(
                source="mysql",
                metric="monthly_revenue",
                data=data,
                row_count=len(data),
                execution_time_ms=duration,
            )
        except Exception as e:
            return MCPToolResult(source="mysql", metric="monthly_revenue", error=str(e))

    def get_sales_by_product(
        self,
        limit: int = 10,
        status: str = "Completed",
    ) -> MCPToolResult:
        """Retrieves total sales, quantity, and revenue grouped by product."""
        start_time = time.time()
        if status not in VALID_STATUSES:
            return MCPToolResult(source="mysql", error=f"Invalid status '{status}'.")
        limit = max(1, min(limit, 50))

        query = """
            SELECT 
                product_name,
                product_category,
                ROUND(SUM(revenue), 2) AS total_revenue,
                SUM(quantity) AS units_sold,
                COUNT(DISTINCT order_id) AS order_frequency
            FROM order_revenue
            WHERE order_status = %s
            GROUP BY product_name, product_category
            ORDER BY total_revenue DESC
            LIMIT %s;
        """
        try:
            raw_data = self.mysql.execute_query(query, (status, limit))
            data = [_serialize_row(r) for r in raw_data]
            duration = round((time.time() - start_time) * 1000, 2)
            return MCPToolResult(
                source="mysql",
                metric="sales_by_product",
                data=data,
                row_count=len(data),
                execution_time_ms=duration,
            )
        except Exception as e:
            return MCPToolResult(source="mysql", metric="sales_by_product", error=str(e))

    def compare_segments_revenue(
        self,
        status: str = "Completed",
    ) -> MCPToolResult:
        """Compares total revenue and order metrics across customer segments (Enterprise vs SMB vs Mid-Market)."""
        start_time = time.time()
        if status not in VALID_STATUSES:
            return MCPToolResult(source="mysql", error=f"Invalid status '{status}'.")

        query = """
            SELECT 
                customer_segment,
                ROUND(SUM(revenue), 2) AS total_revenue,
                COUNT(DISTINCT customer_id) AS customer_count,
                COUNT(DISTINCT order_id) AS order_count,
                ROUND(SUM(revenue) / COUNT(DISTINCT customer_id), 2) AS avg_revenue_per_customer
            FROM order_revenue
            WHERE order_status = %s
            GROUP BY customer_segment
            ORDER BY total_revenue DESC;
        """
        try:
            raw_data = self.mysql.execute_query(query, (status,))
            data = [_serialize_row(r) for r in raw_data]
            duration = round((time.time() - start_time) * 1000, 2)
            return MCPToolResult(
                source="mysql",
                metric="segment_comparison",
                data=data,
                row_count=len(data),
                execution_time_ms=duration,
            )
        except Exception as e:
            return MCPToolResult(source="mysql", metric="segment_comparison", error=str(e))

    def get_top_customers(
        self,
        limit: int = 10,
        status: str = "Completed",
    ) -> MCPToolResult:
        """Retrieves top customers ranked by total enterprise spend."""
        start_time = time.time()
        if status not in VALID_STATUSES:
            return MCPToolResult(source="mysql", error=f"Invalid status '{status}'.")
        limit = max(1, min(limit, 50))

        # Masking PII by returning corporate business names and segments, no personal emails or phone numbers
        query = """
            SELECT 
                customer_name,
                customer_segment,
                industry,
                region_name,
                ROUND(SUM(revenue), 2) AS total_spent,
                COUNT(DISTINCT order_id) AS total_orders
            FROM order_revenue
            WHERE order_status = %s
            GROUP BY customer_id, customer_name, customer_segment, industry, region_name
            ORDER BY total_spent DESC
            LIMIT %s;
        """
        try:
            raw_data = self.mysql.execute_query(query, (status, limit))
            data = [_serialize_row(r) for r in raw_data]
            duration = round((time.time() - start_time) * 1000, 2)
            return MCPToolResult(
                source="mysql",
                metric="top_customers",
                data=data,
                row_count=len(data),
                execution_time_ms=duration,
            )
        except Exception as e:
            return MCPToolResult(source="mysql", metric="top_customers", error=str(e))

    def get_overall_summary(self) -> MCPToolResult:
        """Retrieves executive headline KPIs (Total Revenue, Total Orders, Average Order Value)."""
        start_time = time.time()
        query = """
            SELECT 
                ROUND(SUM(revenue), 2) AS total_revenue,
                COUNT(DISTINCT order_id) AS total_completed_orders,
                COUNT(DISTINCT customer_id) AS active_customers,
                ROUND(SUM(revenue) / COUNT(DISTINCT order_id), 2) AS avg_order_value
            FROM order_revenue
            WHERE order_status = 'Completed';
        """
        try:
            raw_data = self.mysql.execute_query(query)
            data = [_serialize_row(r) for r in raw_data]
            duration = round((time.time() - start_time) * 1000, 2)
            return MCPToolResult(
                source="mysql",
                metric="overall_summary",
                data=data,
                row_count=len(data),
                execution_time_ms=duration,
            )
        except Exception as e:
            return MCPToolResult(source="mysql", metric="overall_summary", error=str(e))


# Global Singleton Instance
mysql_mcp = MySQLMCPServer()
