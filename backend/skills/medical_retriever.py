"""
MedMind — Skill 2: Medical Retriever
Multi-query retrieval with local RAG and optional trusted web search.

Philosophy: the local KB is a curated supplement for specific topics.
Trusted web sources (Mayo Clinic, NIH, WHO, etc.) are the primary
knowledge source.  When local results are weak, they are dropped
entirely so they don't pollute the evidence the LLM reasons over.
"""

import statistics
import math
from typing import List, Dict
from rag.vector_db import VectorDB
from rag.reranker import Reranker
from config import (
    TOP_K_RETRIEVAL,
    TOP_K_RERANK,
    ENABLE_WEB_SEARCH,
    TRUSTED_SOURCES
)

# Local results with reranker scores below this are considered irrelevant
# and will be dropped when web results are available.
LOCAL_RELEVANCE_FLOOR = -3.0


class MedicalRetriever:
    """Skill 2: Smart multi-query retrieval with local RAG and trusted web search."""

    def __init__(self, vector_db: VectorDB, reranker: Reranker):
        self.db = vector_db
        self.reranker = reranker
        self.enable_web = ENABLE_WEB_SEARCH
        self.trusted_sources = TRUSTED_SOURCES

    def retrieve(
        self,
        analysis: dict,
        top_k: int = TOP_K_RERANK,
    ) -> list[dict]:
        """
        Retrieve and rerank relevant medical evidence.

        Strategy:
        1. Pull candidates from local KB + trusted web search
        2. Rerank each pool separately against the original query
        3. Drop local results that score below LOCAL_RELEVANCE_FLOOR
           when web results are available (don't pollute evidence)
        4. Web results from trusted sources are always preferred
        """
        sub_queries = analysis.get("sub_queries", [])
        original_query = analysis.get("original_query", "")

        if not sub_queries:
            sub_queries = [original_query]

        local_results = []
        web_results_raw = []
        seen_contents = set()

        # Step 1: Local RAG Retrieval
        for query in sub_queries:
            results = self.db.search(query, n_results=TOP_K_RETRIEVAL)
            for result in results:
                content_key = result["content"][:200]
                if content_key not in seen_contents:
                    seen_contents.add(content_key)
                    local_results.append(result)

        # Step 2: Trusted Web Search (if enabled)
        if self.enable_web:
            web_results_raw = self._web_search(sub_queries[:2])
            for result in web_results_raw:
                content_key = result["content"][:200]
                if content_key not in seen_contents:
                    seen_contents.add(content_key)

        if not local_results and not web_results_raw:
            return []

        # Step 3: Rerank each pool separately
        local_reranked = self.reranker.rerank(
            query=original_query,
            results=local_results,
            top_k=top_k,
        ) if local_results else []

        web_reranked = self.reranker.rerank(
            query=original_query,
            results=web_results_raw,
            top_k=top_k,
        ) if web_results_raw else []

        # Step 4: Smart merge — drop weak local results when web has answers
        merged = self._smart_merge(local_reranked, web_reranked, top_k)

        # Step 5: Assign source labels [S1], [S2], etc.
        for i, result in enumerate(merged):
            result["source_label"] = f"S{i + 1}"
            src_type = "WEB" if result.get("section") == "Web Search Result" else "LOCAL"
            print(f"  [Source {i+1}] [{src_type}] Score: {result.get('rerank_score', 0.0):.4f} - {result['document_title']}", flush=True)

        return merged

    def _smart_merge(
        self,
        local: list[dict],
        web: list[dict],
        top_k: int,
    ) -> list[dict]:
        """
        Merge local and web results intelligently.

        Rules:
        - If no web results, use local as-is (offline mode).
        - If web results exist, only keep local results that score
          ABOVE LOCAL_RELEVANCE_FLOOR (i.e. actually relevant).
        - Web results from trusted medical sources always get priority.
        - Final list sorted by score, capped at top_k.
        """
        if not web:
            # Offline mode — local is all we have
            return local[:top_k]

        if not local:
            # No local KB — web only
            return web[:top_k]

        # Filter: only keep local results that are actually relevant.
        # If a local chunk scores below the floor, it's noise — drop it.
        strong_local = [
            r for r in local
            if r.get("rerank_score", r.get("score", -999)) >= LOCAL_RELEVANCE_FLOOR
        ]

        if strong_local:
            print(f"  [Merge] Keeping {len(strong_local)}/{len(local)} local results (score >= {LOCAL_RELEVANCE_FLOOR})", flush=True)
        else:
            print(f"  [Merge] All local results below {LOCAL_RELEVANCE_FLOOR} — using web only", flush=True)

        # Combine strong local + all web, sort by score
        combined = strong_local + web
        combined.sort(
            key=lambda x: x.get("rerank_score", x.get("score", -999)),
            reverse=True,
        )

        return combined[:top_k]

    def _web_search(self, queries: List[str]) -> List[Dict]:
        """Perform a restricted web search on trusted medical domains."""
        results = []
        try:
            # Try new package name first, fall back to old one
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS
            site_filter = " OR ".join([f"site:{s}" for s in self.trusted_sources])

            with DDGS() as ddgs:
                for query in queries:
                    search_query = f"{query} ({site_filter})"
                    print(f"[WebSearch] Query: {search_query}", flush=True)
                    
                    ddgs_results = ddgs.text(search_query, max_results=3)
                    if ddgs_results:
                        for r in ddgs_results:
                            results.append({
                                "content": f"{r['title']}: {r['body']}",
                                "source": self._identify_source(r['href']),
                                "source_url": r['href'],
                                "document_title": r['title'],
                                "section": "Web Search Result",
                                "score": 0.5,
                            })
        except Exception as e:
            print(f"[WebSearch] Error: {e}", flush=True)
            
        return results

    def _identify_source(self, url: str) -> str:
        """Extract a clean source name from the URL."""
        for source in self.trusted_sources:
            if source in url.lower():
                return source.capitalize()
        return "Trusted Web Source"

    def get_retrieval_confidence(self, results: list[dict]) -> float:
        """
        Calculate overall retrieval confidence.

        The ms-marco cross-encoder outputs raw logits roughly in [-10, +10].
        Moderately relevant pairs typically score -3 to +2.  We use a sigmoid
        with a center offset of +5 so that:
            score -4.5 → confidence ~0.58  (partial match — still usable)
            score -2   → confidence ~0.95
            score  0   → confidence ~0.99
        This prevents the system from refusing everything.

        Bonus: if trusted web results are present, we boost confidence because
        the LLM can reason over real medical website content even when reranker
        scores are modest.
        """
        if not results:
            return 0.0

        scores = [r.get("rerank_score", r.get("score", 0.0)) for r in results]

        top_score = scores[0] if scores else -10.0

        # Average the top-3 non-garbage scores
        significant_scores = [s for s in scores if s > -8.0]
        if not significant_scores:
            significant_scores = [top_score]

        avg_score = statistics.mean(significant_scores[:3])

        # Weighted blend: 70% top score, 30% average
        confidence_val = (0.70 * top_score) + (0.30 * avg_score)

        # Sigmoid with offset +5 — centers the curve on typical cross-encoder scores
        base_confidence = 1.0 / (1.0 + math.exp(-(confidence_val + 5.0)))

        # Boost: if we have web results from trusted sources, the LLM has
        # real content to reason over even when local KB is weak
        has_web = any(r.get("section") == "Web Search Result" for r in results)
        if has_web and base_confidence < 0.6:
            base_confidence = max(base_confidence, 0.55)

        return base_confidence

    def format_evidence_for_prompt(self, results: list[dict]) -> str:
        """Format retrieved evidence into a prompt-ready string."""
        if not results:
            return "No relevant evidence found."

        parts = []
        for result in results:
            label = result.get("source_label", "S?")
            source = result.get("source", "Unknown")
            section = result.get("section", "")
            source_url = result.get("source_url", "")
            content = result["content"]

            part = f"""--- [{label}] {source} ---
Section: {section}
URL: {source_url}
Content:
{content}
---"""
            parts.append(part)

        return "\n\n".join(parts)
