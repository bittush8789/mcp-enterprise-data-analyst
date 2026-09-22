"""Deterministic Analytics Engine for MCP Enterprise Data Analyst.

Uses Pandas to perform deterministic mathematical calculations:
- Sum, Mean/Average, Min, Max
- Segment & Region Rankings
- Percentage shares / distribution
- Month-over-Month (MoM) Growth rates
- Period comparisons & trend detection
- Visualization configurations generation for frontend charts
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

from backend.models.schemas import VisualizationConfig

logger = logging.getLogger("enterprise_analyst.analytics")


class AnalyticsEngine:
    """Computes exact, deterministic analytics over structured datasets."""

    def analyze_dataset(
        self,
        data: List[Dict[str, Any]],
        metric_type: str,
    ) -> Dict[str, Any]:
        """Computes summary statistics and deterministic insights using Pandas."""
        if not data:
            return {"empty": True, "summary": "Dataset is empty."}

        df = pd.DataFrame(data)

        # Identify numeric and category columns
        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        categorical_cols = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]

        summary: Dict[str, Any] = {
            "row_count": len(df),
            "columns": list(df.columns),
            "metrics": {},
        }

        # 1. Deterministic Aggregations on Primary Metric
        primary_metric = next((c for c in ["total_revenue", "revenue", "monthly_revenue", "total_spent", "units_sold"] if c in df.columns), None)
        if not primary_metric and numeric_cols:
            primary_metric = numeric_cols[0]

        if primary_metric:
            series = df[primary_metric]
            total_sum = float(series.sum())
            mean_val = float(series.mean())
            min_val = float(series.min())
            max_val = float(series.max())

            summary["metrics"][primary_metric] = {
                "sum": round(total_sum, 2),
                "average": round(mean_val, 2),
                "min": round(min_val, 2),
                "max": round(max_val, 2),
            }

            # 2. Percentage Distribution if Category exists
            cat_col = next((c for c in ["region_name", "customer_segment", "product_name", "month"] if c in df.columns), None)
            if cat_col:
                if total_sum > 0:
                    df["share_pct"] = (df[primary_metric] / total_sum * 100).round(2)
                    summary["distribution"] = df[[cat_col, primary_metric, "share_pct"]].to_dict(orient="records")

                # Rankings
                ranked_df = df.sort_values(by=primary_metric, ascending=False).reset_index(drop=True)
                top_item = ranked_df.iloc[0]
                summary["top_performer"] = {
                    "category": top_item[cat_col],
                    "value": float(top_item[primary_metric]),
                    "rank": 1,
                }

            # 3. Growth & Trend calculation if time series (monthly data)
            if "month" in df.columns:
                df_sorted = df.sort_values(by="month").reset_index(drop=True)
                df_sorted["mom_growth_pct"] = df_sorted[primary_metric].pct_change().mul(100).round(2)
                growth_list = df_sorted[["month", primary_metric, "mom_growth_pct"]].to_dict(orient="records")
                summary["growth_trend"] = growth_list

                # Overall trend direction
                if len(df_sorted) >= 2:
                    first_val = float(df_sorted.iloc[0][primary_metric])
                    last_val = float(df_sorted.iloc[-1][primary_metric])
                    pct_change = round(((last_val - first_val) / first_val * 100), 2) if first_val > 0 else 0.0
                    summary["overall_trend"] = {
                        "first_period": df_sorted.iloc[0]["month"],
                        "last_period": df_sorted.iloc[-1]["month"],
                        "period_change_pct": pct_change,
                        "direction": "upward" if pct_change > 0 else "downward" if pct_change < 0 else "flat",
                    }

        return summary

    def build_visualization(
        self,
        data: List[Dict[str, Any]],
        metric_name: Optional[str] = None,
    ) -> Optional[VisualizationConfig]:
        """Constructs interactive chart configurations for the frontend."""
        if not data:
            return None

        df = pd.DataFrame(data)

        # Case 1: Overall Summary Single KPI
        if "total_completed_orders" in df.columns and "total_revenue" in df.columns:
            tot_rev = float(df.iloc[0]["total_revenue"])
            return VisualizationConfig(
                type="kpi",
                title="Enterprise Total Completed Revenue",
                kpi_value=f"${tot_rev:,.2f}",
                kpi_label="Total Verified Revenue",
            )

        # Case 2: Monthly Timeline Line Chart
        if "month" in df.columns and "monthly_revenue" in df.columns:
            df_sorted = df.sort_values(by="month")
            return VisualizationConfig(
                type="line",
                title="Monthly Enterprise Revenue Trend",
                x=df_sorted["month"].tolist(),
                y=[float(v) for v in df_sorted["monthly_revenue"].tolist()],
            )

        # Case 3: Region Revenue Bar Chart
        if "region_name" in df.columns and "total_revenue" in df.columns:
            df_sorted = df.sort_values(by="total_revenue", ascending=False)
            return VisualizationConfig(
                type="bar",
                title="Revenue by Geographic Region",
                x=df_sorted["region_name"].tolist(),
                y=[float(v) for v in df_sorted["total_revenue"].tolist()],
            )

        # Case 4: Customer Segment Bar Chart
        if "customer_segment" in df.columns and "total_revenue" in df.columns:
            df_sorted = df.sort_values(by="total_revenue", ascending=False)
            return VisualizationConfig(
                type="bar",
                title="Revenue by Customer Segment",
                x=df_sorted["customer_segment"].tolist(),
                y=[float(v) for v in df_sorted["total_revenue"].tolist()],
            )

        # Case 5: Product Revenue Bar Chart
        if "product_name" in df.columns and "total_revenue" in df.columns:
            df_sorted = df.sort_values(by="total_revenue", ascending=False).head(8)
            return VisualizationConfig(
                type="bar",
                title="Top Products by Enterprise Revenue",
                x=df_sorted["product_name"].tolist(),
                y=[float(v) for v in df_sorted["total_revenue"].tolist()],
            )

        # Case 6: Top Customers Horizontal Bar Chart
        if "customer_name" in df.columns and "total_spent" in df.columns:
            df_sorted = df.sort_values(by="total_spent", ascending=False).head(10)
            return VisualizationConfig(
                type="bar",
                title="Top Enterprise Customers by Revenue",
                x=df_sorted["customer_name"].tolist(),
                y=[float(v) for v in df_sorted["total_spent"].tolist()],
            )

        return None


# Global Singleton Instance
analytics_engine = AnalyticsEngine()
