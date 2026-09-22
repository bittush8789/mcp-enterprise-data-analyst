"""Reranker Module for Hybrid RAG.

Provides precision reranking for candidate chunks using hybrid score fusion,
exact-term density weighting, and cross-relevance scoring.
"""

import re
import logging
from typing import Any, Dict, List, Optional

from backend.config import settings

logger = logging.getLogger("enterprise_analyst.reranker")


class Reranker:
    """Reranks candidate document chunks to prioritize precise factual answers."""

    def __init__(self, enabled: Optional[bool] = None):
        self.enabled = enabled if enabled is not None else settings.RERANKER_ENABLED

    def _calculate_relevance(self, query: str, chunk_text: str, base_score: float) -> float:
        """Calculates a fine-grained relevance score combining base fusion with exact matches."""
        score = base_score
        q_tokens = [t.lower() for t in re.findall(r"\b[\w\$\%\.\-]+\b", query) if len(t) > 1]
        text_lower = chunk_text.lower()

        if not q_tokens:
            return score

        # 1. Exact term matches (numbers, dollar amounts, acronyms like SLA, SOP, Sev)
        exact_matches = 0
        for token in q_tokens:
            if token in text_lower:
                exact_matches += 1
                # Heavily reward exact numbers/percentages (e.g. 30, 99.99%, 15%)
                if re.match(r"^[\$\%0-9\.]+$", token):
                    score += 0.15

        coverage_ratio = exact_matches / len(q_tokens)
        score += coverage_ratio * 0.25

        # 2. Check for exact phrase matching (bigram / trigram)
        query_clean = " ".join(q_tokens)
        if len(query_clean) > 8 and query_clean in text_lower:
            score += 0.30

        # 3. Header bonus: if match appears in first 100 chars (title/header)
        first_part = text_lower[:120]
        if any(t in first_part for t in q_tokens):
            score += 0.10

        return score

    def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Reranks candidates and returns the top_k most relevant chunks."""
        if not candidates:
            return []

        k = top_k or settings.TOP_K

        if not self.enabled:
            return candidates[:k]

        reranked = []
        for cand in candidates:
            base_score = cand.get("score", cand.get("hybrid_score", 0.5))
            content = cand.get("content", "")
            final_score = self._calculate_relevance(query, content, base_score)
            item = dict(cand)
            item["rerank_score"] = round(final_score, 4)
            reranked.append(item)

        # Sort descending by rerank_score
        reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
        return reranked[:k]


# Global Singleton Instance
reranker = Reranker()
