"""
MedMind — Vector Database
ChromaDB-backed vector store for medical knowledge retrieval.
All data persisted locally — nothing leaves your machine.
"""

import hashlib
import uuid
import chromadb
from typing import Optional

from config import CHROMA_DIR, MEDICAL_COLLECTION, USER_DOCS_COLLECTION
from rag.embedder import Embedder


class VectorDB:
    """Local vector database for storing and searching medical knowledge."""

    def __init__(self):
        self.client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        self.embedder = Embedder()

        # Two collections: built-in medical KB and user-uploaded docs
        self.medical = self.client.get_or_create_collection(
            name=MEDICAL_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        self.user_docs = self.client.get_or_create_collection(
            name=USER_DOCS_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

        print(f"[VectorDB] Medical KB: {self.medical.count()} chunks")
        print(f"[VectorDB] User docs:  {self.user_docs.count()} chunks")

    def add_medical_chunks(self, chunks: list[dict]) -> int:
        """
        Add chunks from the built-in medical knowledge base.

        Args:
            chunks: List of dicts with keys:
                - content: The text content
                - section: Section/category name
                - document_title: Source document title
                - source: Source name (e.g., "WHO", "MedlinePlus")
                - source_url: URL of the original source
                - chunk_index: Index within the document

        Returns:
            Number of chunks successfully added
        """
        return self._add_chunks(self.medical, chunks, source_type="medical_kb")

    def add_user_document(self, chunks: list[dict], filename: str) -> int:
        """
        Add chunks from a user-uploaded document.

        Args:
            chunks: List of dicts with 'content', 'section', 'chunk_index' keys
            filename: Original filename for metadata

        Returns:
            Number of chunks successfully added
        """
        for chunk in chunks:
            chunk["source"] = f"Uploaded: {filename}"
            chunk["source_url"] = ""
        return self._add_chunks(self.user_docs, chunks, source_type="user_upload")

    @staticmethod
    def _make_chunk_id(chunk: dict, source_type: str) -> str:
        """Deterministic ID so re-running ingest is idempotent (upsert)."""
        key = "|".join([
            source_type,
            str(chunk.get("source", "")),
            str(chunk.get("document_title", "")),
            str(chunk.get("section", "")),
            str(chunk.get("chunk_index", 0)),
            chunk.get("content", "")[:200],
        ])
        return hashlib.sha1(key.encode("utf-8")).hexdigest()

    def _add_chunks(
        self,
        collection: chromadb.Collection,
        chunks: list[dict],
        source_type: str,
    ) -> int:
        """Internal: upsert chunks into a ChromaDB collection with embeddings."""
        if not chunks:
            return 0

        texts = [c["content"] for c in chunks]
        embeddings = self.embedder.embed_batch(texts)

        valid_ids = []
        valid_embeddings = []
        valid_documents = []
        valid_metadatas = []

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            if not embedding:
                continue

            # User uploads aren't reproducible across runs; keep them random.
            if source_type == "user_upload":
                doc_id = str(uuid.uuid4())
            else:
                doc_id = self._make_chunk_id(chunk, source_type)

            valid_ids.append(doc_id)
            valid_embeddings.append(embedding)
            valid_documents.append(chunk["content"])
            valid_metadatas.append({
                "section": chunk.get("section", "General"),
                "document_title": chunk.get("document_title", "Unknown"),
                "source": chunk.get("source", ""),
                "source_url": chunk.get("source_url", ""),
                "chunk_index": chunk.get("chunk_index", i),
                "source_type": source_type,
            })

        if not valid_ids:
            return 0

        # Upsert in batches (ChromaDB has batch size limits).
        batch_size = 100
        for i in range(0, len(valid_ids), batch_size):
            end = i + batch_size
            collection.upsert(
                ids=valid_ids[i:end],
                embeddings=valid_embeddings[i:end],
                documents=valid_documents[i:end],
                metadatas=valid_metadatas[i:end],
            )

        added = len(valid_ids)
        print(f"[VectorDB] Upserted {added} chunks ({source_type})")
        return added

    def search(
        self,
        query: str,
        n_results: int = 10,
        collection: Optional[str] = None,
    ) -> list[dict]:
        """
        Search for relevant chunks across all collections.

        Args:
            query: Search query text
            n_results: Maximum results to return
            collection: If set, search only this collection ("medical" or "user")

        Returns:
            List of result dicts sorted by relevance score, each containing:
            - content, section, source, source_url, score, chunk_index
        """
        query_embedding = self.embedder.embed_query(query)
        if not query_embedding:
            return []

        results = []

        # Search selected collections
        collections_to_search = []
        if collection == "medical" or collection is None:
            collections_to_search.append(self.medical)
        if collection == "user" or collection is None:
            collections_to_search.append(self.user_docs)

        for coll in collections_to_search:
            if coll.count() == 0:
                continue

            search_n = min(n_results, coll.count())
            try:
                response = coll.query(
                    query_embeddings=[query_embedding],
                    n_results=search_n,
                    include=["documents", "metadatas", "distances"],
                )
            except Exception as e:
                print(f"[VectorDB] Search error: {e}")
                continue

            if not response["ids"] or not response["ids"][0]:
                continue

            for i, doc_id in enumerate(response["ids"][0]):
                # ChromaDB returns cosine distance; convert to similarity
                distance = response["distances"][0][i]
                score = 1.0 - distance  # cosine similarity = 1 - cosine distance

                metadata = response["metadatas"][0][i]
                results.append({
                    "content": response["documents"][0][i],
                    "section": metadata.get("section", ""),
                    "document_title": metadata.get("document_title", ""),
                    "source": metadata.get("source", ""),
                    "source_url": metadata.get("source_url", ""),
                    "chunk_index": metadata.get("chunk_index", 0),
                    "source_type": metadata.get("source_type", ""),
                    "score": round(score, 4),
                })

        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:n_results]

    def count(self) -> dict:
        """Return document counts for all collections."""
        return {
            "medical_kb": self.medical.count(),
            "user_documents": self.user_docs.count(),
            "total": self.medical.count() + self.user_docs.count(),
        }

    def clear_user_documents(self):
        """Clear all user-uploaded documents (keep medical KB)."""
        self.client.delete_collection(USER_DOCS_COLLECTION)
        self.user_docs = self.client.get_or_create_collection(
            name=USER_DOCS_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        print("[VectorDB] User documents cleared")

    def clear_all(self):
        """Clear everything — use with caution."""
        self.client.delete_collection(MEDICAL_COLLECTION)
        self.client.delete_collection(USER_DOCS_COLLECTION)
        self.medical = self.client.get_or_create_collection(
            name=MEDICAL_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        self.user_docs = self.client.get_or_create_collection(
            name=USER_DOCS_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        print("[VectorDB] All data cleared")
