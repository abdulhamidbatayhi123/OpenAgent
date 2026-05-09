"""
MedMind — Cross-Encoder Reranker
Uses a small cross-encoder model to rerank retrieved chunks by true relevance.

This is the "secret weapon" — cosine similarity is fast but approximate.
A cross-encoder scores each (query, document) pair directly, giving much
more accurate relevance scores. The model is only ~100MB.
"""

from config import ENABLE_RERANKER, TOP_K_RERANK


class Reranker:
    """Rerank retrieved chunks using a cross-encoder model."""

    def __init__(self):
        self.model = None
        self.enabled = ENABLE_RERANKER

        if self.enabled:
            self._load_model()

    def _load_model(self):
        """Lazy-load the cross-encoder model."""
        try:
            from sentence_transformers import CrossEncoder

            self.model = CrossEncoder(
                "cross-encoder/ms-marco-MiniLM-L-6-v2",
                max_length=512,
            )
            print("[Reranker] Loaded cross-encoder/ms-marco-MiniLM-L-6-v2")
        except ImportError:
            print("[Reranker] sentence-transformers not installed. Reranking disabled.")
            self.enabled = False
        except Exception as e:
            print(f"[Reranker] Failed to load model: {e}")
            self.enabled = False

    def rerank(
        self,
        query: str,
        results: list[dict],
        top_k: int = TOP_K_RERANK,
    ) -> list[dict]:
        """
        Rerank search results using the cross-encoder.

        Args:
            query: The original search query
            results: List of result dicts (must have 'content' key)
            top_k: Number of top results to return after reranking

        Returns:
            Reranked list of results (best first), trimmed to top_k
        """
        if not self.enabled or not self.model or not results:
            return results[:top_k]

        # Create (query, document) pairs for the cross-encoder
        pairs = [(query, r["content"]) for r in results]

        try:
            scores = self.model.predict(pairs)

            # Attach rerank scores to results
            for i, score in enumerate(scores):
                results[i]["rerank_score"] = float(score)

            # Sort by rerank score (higher = more relevant)
            reranked = sorted(results, key=lambda x: x["rerank_score"], reverse=True)

            return reranked[:top_k]
        except Exception as e:
            print(f"[Reranker] Error: {e}")
            return results[:top_k]
