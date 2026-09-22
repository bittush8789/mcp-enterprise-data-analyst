"""Unit Tests for MySQL MCP and ChromaDB MCP Servers."""

import pytest
from backend.mcp.mysql_server import mysql_mcp
from backend.mcp.chroma_server import chroma_mcp


class TestMCPServers:
    def test_mysql_mcp_revenue_by_region(self):
        res = mysql_mcp.get_revenue_by_region(status="Completed")
        assert res.source == "mysql"
        assert res.metric == "revenue_by_region"
        assert res.error is None
        assert res.data is not None
        assert len(res.data) == 5
        assert "region_name" in res.data[0]
        assert "total_revenue" in res.data[0]
        assert res.data[0]["total_revenue"] > 0

    def test_mysql_mcp_invalid_status_rejection(self):
        res = mysql_mcp.get_revenue_by_region(status="DROP TABLE")
        assert res.source == "mysql"
        assert res.error is not None
        assert "Invalid status" in res.error

    def test_mysql_mcp_monthly_revenue(self):
        res = mysql_mcp.get_monthly_revenue(months=6)
        assert res.source == "mysql"
        assert res.metric == "monthly_revenue"
        assert res.data is not None
        assert len(res.data) > 0
        assert "month" in res.data[0]
        assert "monthly_revenue" in res.data[0]

    def test_mysql_mcp_sales_by_product(self):
        res = mysql_mcp.get_sales_by_product(limit=5)
        assert res.source == "mysql"
        assert res.metric == "sales_by_product"
        assert res.data is not None
        assert len(res.data) <= 5
        assert "product_name" in res.data[0]
        assert "total_revenue" in res.data[0]

    def test_mysql_mcp_compare_segments_revenue(self):
        res = mysql_mcp.compare_segments_revenue()
        assert res.source == "mysql"
        assert res.metric == "segment_comparison"
        assert res.data is not None
        segments = [r["customer_segment"] for r in res.data]
        assert "Enterprise" in segments
        assert "SMB" in segments

    def test_mysql_mcp_top_customers(self):
        res = mysql_mcp.get_top_customers(limit=10)
        assert res.source == "mysql"
        assert res.metric == "top_customers"
        assert res.data is not None
        assert len(res.data) <= 10
        assert "customer_name" in res.data[0]
        assert "total_spent" in res.data[0]
        # PII Protection: verify personal emails and phones are not in output
        assert "email" not in res.data[0]
        assert "phone" not in res.data[0]

    def test_chroma_mcp_search_documents(self):
        res = chroma_mcp.search_business_documents("What is our refund policy?", top_k=3)
        assert res.source == "chroma"
        assert res.metric == "document_search"
        assert res.results is not None
        assert len(res.results) > 0
        assert "content" in res.results[0]
        assert "score" in res.results[0]
        assert "metadata" in res.results[0]

    def test_chroma_mcp_search_policy(self):
        res = chroma_mcp.search_policy("discount rules for enterprise accounts", top_k=2)
        assert res.source == "chroma"
        assert res.metric == "policy_search"
        assert len(res.results or []) > 0

    def test_chroma_mcp_search_sop(self):
        res = chroma_mcp.search_sop("Severity 1 incident escalation SLA", top_k=2)
        assert res.source == "chroma"
        assert res.metric == "sop_search"
        assert len(res.results or []) > 0
        sop_hit = any("sop" in r.get("metadata", {}).get("document_slug", "") for r in res.results)
        assert sop_hit
