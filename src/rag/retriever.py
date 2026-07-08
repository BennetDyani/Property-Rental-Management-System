from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from langchain_ollama import OllamaEmbeddings
from src.config import settings
from src.rag.chunking import DocumentChunk, chunk_documents
from src.rag.document import MultimodalDocument
from src.rag.vector_store import VectorStore

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "could", "do",
    "does", "for", "from", "how", "i", "in", "is", "it", "may", "of", "on",
    "or", "should", "the", "their", "there", "this", "to", "use", "was",
    "what", "when", "where", "which", "who", "why", "with",
}


def _tokenize(text: str) -> list[str]:
    return [
        token
        for token in _TOKEN_PATTERN.findall(text.lower())
        if token not in _STOPWORDS
    ]


@dataclass(frozen=True)
class RetrievalResult:
    chunk: DocumentChunk
    score: float
    matched_terms: tuple[str, ...]


class MultimodalRetriever:
    """
    A Hybrid Retriever that combines keyword-based TF-IDF search
    with semantic vector search via pgvector.
    """

    def __init__(
            self,
            vector_store: VectorStore | None = None,
            embedding_model_name: str | None = None,
            ollama_base_url: str | None = None
    ):
        self.chunks: list[DocumentChunk] = []
        self.vector_store = vector_store
        embedding_model_name = embedding_model_name or settings.embedding_model
        ollama_base_url = ollama_base_url or settings.ollama_base_url

        # Initialize the embedding model for semantic search
        try:
            self.embedder = OllamaEmbeddings(
                model=embedding_model_name,
                base_url=ollama_base_url
            )
        except Exception:
            self.embedder = None

    def add_documents(self, documents: list[MultimodalDocument], chunk_size: int = 100, chunk_overlap: int = 20):
        chunks = chunk_documents(documents, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.add_chunks(chunks)
        return chunks

    def add_chunks(self, chunks: list[DocumentChunk]):
        self.chunks.extend(chunks)

    def _get_keyword_score(self, query_tokens: list[str], chunk: DocumentChunk) -> tuple[float, tuple[str, ...]]:
        """Calculates a simple TF-IDF like score for keyword matching."""
        chunk_tokens = _tokenize(chunk.text)
        chunk_counts = Counter(chunk_tokens)

        matched = [t for t in query_tokens if t in chunk_counts]
        if not matched:
            return 0.0, ()

        # Simple score: sum of matched term frequencies normalized by length
        score = sum(chunk_counts[t] for t in matched) / (len(chunk_tokens) + 1)
        return score, tuple(matched)

    def search(
            self,
            query: str,
            top_k: int = 5,
            modality: str | None = None,
            filters: dict[str, Any] | None = None
    ) -> list[RetrievalResult]:
        """
        Hybrid Search: Combines Keyword and Semantic results.
        """
        query_tokens = _tokenize(query)

        # 1. Keyword Search (In-Memory)
        keyword_results = []
        for chunk in self.chunks:
            # Apply filters
            if filters and not all(chunk.metadata.get(k) == v for k, v in filters.items()):
                continue
            if modality and chunk.metadata.get("modality") != modality:
                continue

            score, matched = self._get_keyword_score(query_tokens, chunk)
            if score > 0:
                keyword_results.append({
                    "chunk": chunk,
                    "score": score,
                    "matched": matched
                })

        # 2. Semantic Search (VectorStore)
        vector_results = []
        if self.vector_store and self.embedder:
            try:
                query_vec = self.embedder.embed_query(query)
                db_results = self.vector_store.search_similar(
                    query_embedding=query_vec,
                    top_k=top_k * 2,
                    filters=filters
                )

                for db_chunk, score in db_results:
                    metadata = dict(db_chunk.metadata_json or {})
                    metadata.setdefault("source", db_chunk.document.source_path)
                    metadata.setdefault("modality", db_chunk.document.modality)

                    # Convert DB Model to DTO
                    dto_chunk = DocumentChunk(
                        chunk_id=db_chunk.chunk_id,
                        document_id=str(db_chunk.document_id),
                        source=db_chunk.document.source_path,
                        modality=db_chunk.document.modality,
                        text=db_chunk.content,
                        metadata=metadata,
                    )
                    vector_results.append({
                        "chunk": dto_chunk,
                        "score": score,
                        "matched": ()  # Vectors don't have "matched terms"
                    })
            except Exception as e:
                print(f"Semantic search error: {e}")

        # 3. Hybrid Merging
        # We use a map to combine scores for the same chunk
        combined: dict[str, dict[str, Any]] = {}

        # Weights: 30% Keyword, 70% Semantic
        W_KEYWORD = 0.3
        W_VECTOR = 0.7

        for res in keyword_results:
            cid = res["chunk"].chunk_id
            combined[cid] = {
                "chunk": res["chunk"],
                "score": res["score"] * W_KEYWORD,
                "matched": res["matched"]
            }

        for res in vector_results:
            cid = res["chunk"].chunk_id
            if cid in combined:
                combined[cid]["score"] += res["score"] * W_VECTOR
            else:
                combined[cid] = {
                    "chunk": res["chunk"],
                    "score": res["score"] * W_VECTOR,
                    "matched": res["matched"]
                }

        # Sort by combined score and return top_k
        sorted_results = sorted(
            combined.values(),
            key=lambda x: x["score"],
            reverse=True
        )[:top_k]

        return [
            RetrievalResult(chunk=r["chunk"], score=r["score"], matched_terms=r["matched"])
            for r in sorted_results
        ]


def prepare_rag_prompt(query: str, results: list[RetrievalResult]) -> str:
    """Constructs a prompt with cited context blocks."""
    context_blocks = []
    for i, res in enumerate(results, 1):
        source = res.chunk.metadata.get("source", "unknown")
        modality = res.chunk.metadata.get("modality", "text")
        content = res.chunk.text
        context_blocks.append(f"[{i}] {source} ({modality})\n{content}")

    context_text = "\n\n".join(context_blocks)

    return (
        "Use the retrieved context to answer the question. "
        "Cite the relevant context blocks by their bracketed numbers.\n\n"
        f"Context:\n{context_text}\n\n"
        f"Question: {query}\n\n"
        "Answer:"
    )