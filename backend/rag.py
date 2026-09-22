"""Hybrid RAG Retrieval Engine.

Combines ChromaDB vector semantic search and BM25 keyword search,
applies configurable result fusion, passes candidates through the
reranker, and enforces RAG security sanitization.
"""

import re
import logging
from typing import Any, Dict, List, Optional

from rank_bm25 import BM25Okapi

from backend.config import settings
from backend.chroma import chroma_manager
from backend.reranker import reranker

logger = logging.getLogger("enterprise_analyst.rag")


class HybridRAG:
    """Orchestrates Semantic Search, BM25 Search, Result Fusion, and Reranking."""

    def __init__(self):
        self.chroma = chroma_manager
        self.bm25_index: Optional[BM25Okapi] = None
        self.chunk_corpus: List[Dict[str, Any]] = []
        self._build_bm25_index()

    def _tokenize(self, text: str) -> List[str]:
        """Normalizes and tokenizes text for lexical BM25 matching."""
        return [t.lower() for t in re.findall(r"\b[\w\$\%\.\-]+\b", text) if len(t) > 0]

    def _build_bm25_index(self):
        """Extracts chunks from ChromaDB and compiles the in-memory BM25 index."""
        try:
            raw_data = self.chroma.collection.get()
            if not raw_data or not raw_data.get("documents"):
                logger.warning("No documents retrieved from ChromaDB for BM25 indexing.")
                return

            documents = raw_data["documents"]
            metas = raw_data["metadatas"]
            ids = raw_data["ids"]

            self.chunk_corpus = []
            tokenized_corpus = []

            for chunk_id, doc, meta in zip(ids, documents, metas):
                tokens = self._tokenize(doc)
                tokenized_corpus.append(tokens)
                self.chunk_corpus.append({
                    "id": chunk_id,
                    "content": doc,
                    "metadata": meta,
                })

            if tokenized_corpus:
                self.bm25_index = BM25Okapi(tokenized_corpus)
                logger.info("Compiled BM25 index with %d enterprise document chunks.", len(tokenized_corpus))
        except Exception as e:
            logger.error("Failed to build BM25 index: %s", e)

    def search_bm25(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Executes BM25 keyword search."""
        if not self.bm25_index or not self.chunk_corpus:
            self._build_bm25_index()
            if not self.bm25_index:
                return []

        q_tokens = self._tokenize(query)
        if not q_tokens:
            return []

        doc_scores = self.bm25_index.get_scores(q_tokens)
        max_score = max(doc_scores) if len(doc_scores) > 0 and max(doc_scores) > 0 else 1.0

        scored_chunks = []
        for idx, score in enumerate(doc_scores):
            if score > 0:
                normalized_score = min(1.0, score / max_score)
                chunk = self.chunk_corpus[idx]
                scored_chunks.append({
                    "id": chunk["id"],
                    "content": chunk["content"],
                    "metadata": chunk["metadata"],
                    "bm25_score": round(normalized_score, 4),
                    "raw_bm25": score,
                })

        scored_chunks.sort(key=lambda x: x["bm25_score"], reverse=True)
        return scored_chunks[:top_k]

    def hybrid_search(
        self,
        query: str,
        top_k: Optional[int] = None,
        where_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Performs hybrid retrieval: Semantic + BM25 + Weighted Fusion + Reranker."""
        k = top_k or settings.TOP_K
        candidate_pool_size = max(k * 2, 8)

        # 1. Independent Vector Semantic Search
        semantic_hits = self.chroma.search_semantic(
            query=query,
            top_k=candidate_pool_size,
            where_filter=where_filter,
        )

        # 2. Independent BM25 Keyword Search
        bm25_hits = self.search_bm25(query=query, top_k=candidate_pool_size)

        # 3. Result Fusion (Weighted Combination)
        fused: Dict[str, Dict[str, Any]] = {}

        # Add semantic hits
        for item in semantic_hits:
            cid = item["id"]
            s_score = item.get("score", 0.0)
            fused[cid] = {
                "id": cid,
                "content": item["content"],
                "metadata": item["metadata"],
                "semantic_score": s_score,
                "bm25_score": 0.0,
            }

        # Merge BM25 hits
        for item in bm25_hits:
            cid = item["id"]
            b_score = item.get("bm25_score", 0.0)
            if cid in fused:
                fused[cid]["bm25_score"] = b_score
            else:
                fused[cid] = {
                    "id": cid,
                    "content": item["content"],
                    "metadata": item["metadata"],
                    "semantic_score": 0.0,
                    "bm25_score": b_score,
                }

        # Calculate hybrid weighted score
        sem_weight = settings.SEMANTIC_WEIGHT
        kw_weight = settings.KEYWORD_WEIGHT

        candidate_list = []
        for cid, cand in fused.items():
            hybrid_score = (sem_weight * cand["semantic_score"]) + (kw_weight * cand["bm25_score"])
            cand["score"] = round(hybrid_score, 4)
            cand["hybrid_score"] = cand["score"]
            candidate_list.append(cand)

        # Sort candidate pool before reranking
        candidate_list.sort(key=lambda x: x["score"], reverse=True)

        # 4. Local Cross-Reranking
        final_results = reranker.rerank(query=query, candidates=candidate_list, top_k=k)

        # 5. RAG Security Sanitization: Wrap and sanitize content
        sanitized_results = []
        for res in final_results:
            clean_item = dict(res)
            # Ensure untrusted document content cannot disguise itself as system prompts
            clean_item["content"] = self._sanitize_chunk_content(clean_item["content"])
            sanitized_results.append(clean_item)

        return sanitized_results

    def _sanitize_chunk_content(self, text: str) -> str:
        """Strips or defangs potential prompt injection triggers in document content."""
        # Defang phrases like "ignore previous instructions"
        defanged = re.sub(
            r"(?i)\bignore\s+(all\s+)?(previous|prior)\s+(instructions|system\s+prompts)\b",
            "[REDACTED_SUSPICIOUS_DIRECTIVE]",
            text,
        )
        return defanged


# Global Singleton Instance
rag_engine = HybridRAG()
