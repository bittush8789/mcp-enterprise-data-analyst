"""ChromaDB MCP Server - Enterprise Document Retrieval Tools.

Exposes tools for searching enterprise policies, SOPs, warranties, and SLAs
via Hybrid RAG (Semantic + BM25 + Result Fusion + Reranking).
"""

import time
import logging
from typing import Any, Dict, List, Optional

from backend.config import settings
from backend.rag import rag_engine
from backend.models.schemas import MCPToolResult

logger = logging.getLogger("enterprise_analyst.mcp.chroma")


class ChromaMCPServer:
    """Enterprise Document Knowledge Model Context Protocol Tool Provider."""

    def __init__(self):
        self.rag = rag_engine

    def search_business_documents(
        self,
        query: str,
        top_k: Optional[int] = None,
    ) -> MCPToolResult:
        """Searches all enterprise knowledge base documents using hybrid RAG."""
        start_time = time.time()
        k = top_k or settings.TOP_K

        try:
            results = self.rag.hybrid_search(query=query, top_k=k)
            duration = round((time.time() - start_time) * 1000, 2)
            return MCPToolResult(
                source="chroma",
                metric="document_search",
                results=results,
                row_count=len(results),
                execution_time_ms=duration,
            )
        except Exception as e:
            logger.error("search_business_documents error: %s", e)
            return MCPToolResult(source="chroma", metric="document_search", error=str(e))

    def search_policy(
        self,
        query: str,
        policy_type: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> MCPToolResult:
        """Searches enterprise commercial policies (refund, discount, warranty)."""
        start_time = time.time()
        k = top_k or settings.TOP_K

        where_filter = None
        if policy_type:
            where_filter = {"document_type": policy_type}

        try:
            results = self.rag.hybrid_search(query=query, top_k=k, where_filter=where_filter)
            duration = round((time.time() - start_time) * 1000, 2)
            return MCPToolResult(
                source="chroma",
                metric="policy_search",
                results=results,
                row_count=len(results),
                execution_time_ms=duration,
            )
        except Exception as e:
            logger.error("search_policy error: %s", e)
            return MCPToolResult(source="chroma", metric="policy_search", error=str(e))

    def search_sop(
        self,
        query: str,
        top_k: Optional[int] = None,
    ) -> MCPToolResult:
        """Searches Standard Operating Procedures (SOPs) and incident escalation runbooks."""
        start_time = time.time()
        k = top_k or settings.TOP_K

        try:
            # Query targeted at escalation or SOP documents
            results = self.rag.hybrid_search(
                query=f"SOP standard operating procedure {query}",
                top_k=k,
            )
            # Prioritize escalation_sop chunks if found
            sop_hits = [r for r in results if "sop" in r.get("metadata", {}).get("document_slug", "").lower()]
            final_hits = sop_hits if sop_hits else results

            duration = round((time.time() - start_time) * 1000, 2)
            return MCPToolResult(
                source="chroma",
                metric="sop_search",
                results=final_hits[:k],
                row_count=len(final_hits[:k]),
                execution_time_ms=duration,
            )
        except Exception as e:
            logger.error("search_sop error: %s", e)
            return MCPToolResult(source="chroma", metric="sop_search", error=str(e))


# Global Singleton Instance
chroma_mcp = ChromaMCPServer()
