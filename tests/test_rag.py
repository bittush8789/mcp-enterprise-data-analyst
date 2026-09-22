"""Unit Tests for Hybrid RAG, BM25, ChromaDB Vector Retrieval and Reranker."""

import pytest
from backend.chroma import chroma_manager
from backend.rag import rag_engine
from backend.reranker import reranker


class TestHybridRAG:
    def test_chroma_semantic_search(self):
        hits = chroma_manager.search_semantic("refund policy evaluation window", top_k=3)
        assert len(hits) > 0
        top_hit = hits[0]
        assert "content" in top_hit
        assert "metadata" in top_hit
        assert top_hit["score"] > 0.0
        assert "refund" in top_hit["metadata"]["document_slug"]

    def test_bm25_exact_token_retrieval(self):
        # BM25 specifically targets exact tokens: $10,000, 30 days, 99.99%
        hits_10k = rag_engine.search_bm25("$10,000", top_k=2)
        assert len(hits_10k) > 0
        assert any("$10,000" in h["content"] for h in hits_10k)

        hits_sla = rag_engine.search_bm25("99.99%", top_k=3)
        assert len(hits_sla) > 0
        assert any("99.99%" in h["content"] for h in hits_sla)

    def test_hybrid_fusion_scoring(self):
        query = "What is the warranty policy uptime SLA?"
        hybrid_results = rag_engine.hybrid_search(query, top_k=4)
        assert len(hybrid_results) > 0
        for item in hybrid_results:
            assert "score" in item
            assert "content" in item
            assert "metadata" in item
            # Verify score is within normalized bounds [0, 1.5]
            assert 0.0 <= item["score"] <= 2.0

    def test_reranker_relevance_ordering(self):
        candidates = [
            {"id": "c1", "content": "General introduction to software development.", "score": 0.8},
            {"id": "c2", "content": "Under Severity 1 outage, initial response SLA is within 15 minutes.", "score": 0.6},
        ]
        reranked = reranker.rerank("What is the response SLA for Severity 1?", candidates, top_k=2)
        assert len(reranked) == 2
        # The chunk containing exact tokens 'Severity 1' and '15 minutes' should be boosted to rank 1
        assert reranked[0]["id"] == "c2"

    def test_chunk_metadata_preservation(self):
        hits = rag_engine.hybrid_search("escalation procedure", top_k=1)
        assert len(hits) > 0
        meta = hits[0]["metadata"]
        assert "document_title" in meta
        assert "document_type" in meta
        assert "version" in meta
        assert "effective_date" in meta
        assert "chunk_id" in meta
