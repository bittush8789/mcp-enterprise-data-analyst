"""MySQL Database Access Layer for MCP Enterprise Data Analyst.

Provides safe, parameterized query execution, connection pooling,
timeout enforcement, SQL guard enforcement, and an automatic SQLite
fallback for self-contained testing and offline scenarios.
"""

import os
import re
import time
import logging
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

import pymysql
from pymysql.cursors import DictCursor

from backend.config import settings

logger = logging.getLogger("enterprise_analyst.mysql")

# Blacklist of disallowed SQL statements for read-only enterprise data analytics
DISALLOWED_SQL_PATTERNS = [
    r"\bDROP\b",
    r"\bDELETE\b",
    r"\bUPDATE\b",
    r"\bINSERT\b",
    r"\bALTER\b",
    r"\bTRUNCATE\b",
    r"\bCREATE\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
    r"\bEXEC\b",
    r";\s*\S",  # Prevent multiple statements
]


class MySQLManager:
    """Manages connections to MySQL and provides read-only analytical execution."""

    def __init__(self):
        self.use_sqlite_fallback = False
        self.sqlite_db_path = os.path.join("data", "enterprise_analytics_fallback.db")
        self._check_initial_connectivity()

    def _check_initial_connectivity(self):
        """Attempts to connect to MySQL; flags fallback if unreachable."""
        try:
            conn = self._get_raw_mysql_connection(connect_timeout=2)
            conn.close()
            self.use_sqlite_fallback = False
            logger.info("Successfully connected to MySQL database: %s", settings.MYSQL_DATABASE)
        except Exception as e:
            logger.warning(
                "MySQL not reachable at %s:%s (%s). Enabling local SQLite engine.",
                settings.MYSQL_HOST,
                settings.MYSQL_PORT,
                str(e),
            )
            self.use_sqlite_fallback = True
            self._ensure_sqlite_initialized()

    def _get_raw_mysql_connection(self, connect_timeout: Optional[int] = None):
        timeout = connect_timeout or settings.QUERY_TIMEOUT
        return pymysql.connect(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD,
            database=settings.MYSQL_DATABASE,
            cursorclass=DictCursor,
            connect_timeout=timeout,
            read_timeout=timeout,
            write_timeout=timeout,
            autocommit=True,
        )

    def _ensure_sqlite_initialized(self):
        """Initializes the SQLite fallback database with schema and seed data if needed."""
        os.makedirs("data", exist_ok=True)
        if os.path.exists(self.sqlite_db_path) and os.path.getsize(self.sqlite_db_path) > 100000:
            return

        logger.info("Initializing fallback SQLite database from schema and seed data...")
        conn = sqlite3.connect(self.sqlite_db_path)
        cursor = conn.cursor()

        # Create schema adapted for SQLite
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS regions (
                region_id INTEGER PRIMARY KEY AUTOINCREMENT,
                region_name TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS customers (
                customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                region_id INTEGER NOT NULL,
                customer_segment TEXT NOT NULL,
                industry TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (region_id) REFERENCES regions(region_id)
            );
            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                unit_price REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                order_date TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            );
            CREATE TABLE IF NOT EXISTS order_items (
                order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                unit_price REAL NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(order_id),
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            );
            CREATE VIEW IF NOT EXISTS order_revenue AS
            SELECT 
                oi.order_item_id,
                o.order_id,
                o.order_date,
                o.status AS order_status,
                c.customer_id,
                c.customer_name,
                c.customer_segment,
                c.industry,
                r.region_id,
                r.region_name,
                p.product_id,
                p.product_name,
                p.category AS product_category,
                oi.quantity,
                oi.unit_price,
                ROUND(oi.quantity * oi.unit_price, 2) AS revenue
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
            JOIN customers c ON o.customer_id = c.customer_id
            JOIN regions r ON c.region_id = r.region_id
            JOIN products p ON oi.product_id = p.product_id;
        """)

        # Execute seed SQL if available
        seed_path = os.path.join("data", "seed.sql")
        if os.path.exists(seed_path):
            with open(seed_path, "r", encoding="utf-8") as f:
                seed_sql = f.read()

            # Clean out MySQL specific statements
            statements = [
                s.strip()
                for s in seed_sql.split(";\n")
                if s.strip()
                and not s.strip().startswith("USE ")
                and not s.strip().startswith("SET ")
                and not s.strip().startswith("TRUNCATE ")
            ]
            for stmt in statements:
                try:
                    cursor.execute(stmt)
                except Exception as e:
                    logger.debug("Seed statement skipped in SQLite: %s", str(e))
            conn.commit()
            logger.info("SQLite fallback populated successfully.")
        conn.close()

    def check_health(self) -> Dict[str, Any]:
        """Checks connectivity and returns status information."""
        start_time = time.time()
        if not self.use_sqlite_fallback:
            try:
                conn = self._get_raw_mysql_connection(connect_timeout=2)
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1 AS health_check")
                    result = cursor.fetchone()
                conn.close()
                latency_ms = round((time.time() - start_time) * 1000, 2)
                return {
                    "status": "healthy" if result and result.get("health_check") == 1 else "degraded",
                    "engine": "MySQL",
                    "host": settings.MYSQL_HOST,
                    "database": settings.MYSQL_DATABASE,
                    "latency_ms": latency_ms,
                }
            except Exception as e:
                return {"status": "unhealthy", "engine": "MySQL", "error": str(e)}
        else:
            return {
                "status": "healthy",
                "engine": "SQLite (Fallback Engine Active)",
                "database": self.sqlite_db_path,
                "latency_ms": 0.5,
            }

    def execute_query(
        self,
        query: str,
        params: Optional[Tuple[Any, ...]] = None,
        max_rows: Optional[int] = None,
        timeout: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Executes a parameterized read-only analytical query safely.
        
        Enforces:
        - Read-only SQL safety rules (no DDL/DML)
        - Parameterized query arguments
        - Configured max_rows limit
        - Query timeout enforcement
        """
        # 1. SQL Safety Guard Check
        self._validate_sql_safety(query)

        max_limit = max_rows or settings.MAX_ROWS
        actual_timeout = timeout or settings.QUERY_TIMEOUT
        start_time = time.time()

        if not self.use_sqlite_fallback:
            try:
                conn = self._get_raw_mysql_connection(connect_timeout=actual_timeout)
                with conn.cursor() as cursor:
                    cursor.execute(query, params or ())
                    rows = cursor.fetchmany(max_limit)
                conn.close()
                duration = round((time.time() - start_time) * 1000, 2)
                logger.info("Executed MySQL query in %s ms. Rows returned: %d", duration, len(rows))
                return rows
            except Exception as e:
                logger.error("MySQL query execution failed: %s. Falling back to SQLite.", str(e))
                self.use_sqlite_fallback = True
                self._ensure_sqlite_initialized()

        # Fallback SQLite Execution
        try:
            conn = sqlite3.connect(self.sqlite_db_path, timeout=actual_timeout)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Format %s to ? for SQLite parameterization
            sqlite_query = query.replace("%s", "?")
            cursor.execute(sqlite_query, params or ())
            raw_rows = cursor.fetchmany(max_limit)
            rows = [dict(row) for row in raw_rows]
            conn.close()
            duration = round((time.time() - start_time) * 1000, 2)
            logger.info("Executed query via fallback in %s ms. Rows: %d", duration, len(rows))
            return rows
        except Exception as err:
            logger.error("Database query failed: %s", str(err))
            raise RuntimeError(f"Database query execution error: {str(err)}")

    def _validate_sql_safety(self, query: str):
        """Rejects dangerous SQL commands to prevent SQL injection and state mutation."""
        query_upper = query.upper().strip()

        # Must start with SELECT or WITH
        if not (query_upper.startswith("SELECT") or query_upper.startswith("WITH")):
            raise PermissionError("Security Guardrail: Only SELECT/WITH analytical queries are permitted.")

        for pattern in DISALLOWED_SQL_PATTERNS:
            if re.search(pattern, query_upper):
                raise PermissionError(f"Security Guardrail: Query rejected due to forbidden token matching '{pattern}'.")


# Global Singleton Instance
mysql_manager = MySQLManager()
