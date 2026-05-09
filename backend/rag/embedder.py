"""
MedMind — Local Embedding Engine
Generates vector embeddings using Ollama's local embedding models.
No API keys, no cloud — everything stays on your machine.
"""

import ollama

from config import EMBEDDING_MODEL, OLLAMA_HOST


class Embedder:
    """Generate embeddings locally via Ollama."""

    def __init__(self):
        self.client = ollama.Client(host=OLLAMA_HOST)
        self.model = EMBEDDING_MODEL
        print(f"[Embedder] Using model: {self.model}")

    def embed_text(self, text: str) -> list[float]:
        """
        Generate an embedding vector for a single text.

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector
        """
        if not text or not text.strip():
            return []

        # Truncate very long texts (embedding models have limits)
        if len(text) > 8000:
            text = text[:8000]

        try:
            response = self.client.embed(model=self.model, input=text)
            return response.embeddings[0]
        except Exception as e:
            print(f"[Embedder] Error: {e}")
            return []

    def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """
        Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of texts to embed
            batch_size: How many to embed at once

        Returns:
            List of embedding vectors (same order as input)
        """
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            # Filter empty strings
            batch = [t[:8000] if len(t) > 8000 else t for t in batch if t.strip()]

            if not batch:
                all_embeddings.extend([[] for _ in range(len(texts[i : i + batch_size]))])
                continue

            try:
                response = self.client.embed(model=self.model, input=batch)
                all_embeddings.extend(response.embeddings)
            except Exception as e:
                print(f"[Embedder] Batch error at {i}: {e}")
                all_embeddings.extend([[] for _ in batch])

            if (i + batch_size) % 100 == 0 and i > 0:
                print(f"[Embedder] Embedded {i + batch_size}/{len(texts)} texts")

        return all_embeddings

    def embed_query(self, query: str) -> list[float]:
        """
        Generate an embedding for a search query.
        Alias for embed_text — kept separate for semantic clarity
        and potential future query-specific optimization.
        """
        return self.embed_text(query)
