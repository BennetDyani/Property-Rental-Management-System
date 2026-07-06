from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from math import log
from typing import Any

from src.rag.chunking import DocumentChunk, chunk_documents
from src.rag.document import MultimodalDocument

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.lower())


@dataclass(frozen=True)
class RetrievalResult:
    chunk: DocumentChunk
    score: float
    matched_terms: tuple[str, ...]


class MultimodalRetriever:
    def __init__(self, chunks: list[DocumentChunk] | None = None) -> None:
        self._chunks: list[DocumentChunk] = []
        self._document_frequency: Counter[str] = Counter()
        if chunks:
            self.add_chunks(chunks)

    @property
    def chunks(self) -> list[DocumentChunk]:
        return list(self._chunks)

    def add_documents(
        self,
        documents: list[MultimodalDocument],
        *,
        chunk_size: int = 120,
        chunk_overlap: int = 20,
    ) -> None:
        self.add_chunks(
            chunk_documents(
                documents,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        )

    def add_chunks(self, chunks: list[DocumentChunk]) -> None:
        for chunk in chunks:
            self._chunks.append(chunk)
            unique_tokens = set(_tokenize(chunk.text))
            self._document_frequency.update(unique_tokens)

    def _inverse_document_frequency(self, token: str) -> float:
        total_chunks = len(self._chunks)
        return log((1 + total_chunks) / (1 + self._document_frequency[token])) + 1.0

    def _matches_filters(self, chunk: DocumentChunk, filters: dict[str, Any] | None) -> bool:
        if not filters:
            return True
        return all(chunk.metadata.get(key) == value for key, value in filters.items())

    def search(
        self,
        query: str,
        *,
        top_k: int = 4,
        modality: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievalResult]:
        if top_k < 1:
            raise ValueError("top_k must be at least 1")

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        query_counter = Counter(query_tokens)
        scored_results: list[RetrievalResult] = []

        for chunk in self._chunks:
            if modality is not None and chunk.modality != modality:
                continue
            if not self._matches_filters(chunk, filters):
                continue

            chunk_tokens = _tokenize(chunk.text)
            if not chunk_tokens:
                continue

            chunk_counter = Counter(chunk_tokens)
            matched_terms = [token for token in query_counter if token in chunk_counter]
            if not matched_terms:
                continue

            score = 0.0
            for token in matched_terms:
                score += (
                    query_counter[token]
                    * chunk_counter[token]
                    * self._inverse_document_frequency(token)
                )

            normalized_score = round(score / len(chunk_tokens), 6)
            scored_results.append(
                RetrievalResult(
                    chunk=chunk,
                    score=normalized_score,
                    matched_terms=tuple(sorted(matched_terms)),
                )
            )

        scored_results.sort(
            key=lambda result: (
                result.score,
                len(result.matched_terms),
                result.chunk.metadata.get("chunk_index", 0) * -1,
            ),
            reverse=True,
        )
        return scored_results[:top_k]

    def build_context(
        self,
        query: str,
        *,
        top_k: int = 4,
        modality: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> str:
        results = self.search(
            query,
            top_k=top_k,
            modality=modality,
            filters=filters,
        )
        if not results:
            return ""

        sections: list[str] = []
        for index, result in enumerate(results, start=1):
            citation = f"[{index}] {result.chunk.source} ({result.chunk.modality})"
            sections.append(f"{citation}\n{result.chunk.text}")
        return "\n\n".join(sections)


def prepare_rag_prompt(
    query: str,
    retriever: MultimodalRetriever,
    *,
    top_k: int = 4,
    modality: str | None = None,
    filters: dict[str, Any] | None = None,
) -> str:
    context = retriever.build_context(
        query,
        top_k=top_k,
        modality=modality,
        filters=filters,
    )
    if not context:
        return f"Question: {query}\n\nContext: No matching context found."

    return (
        "Use the retrieved context to answer the question. Cite the relevant "
        "context blocks by their bracketed numbers.\n\n"
        f"Question: {query}\n\n"
        f"Context:\n{context}"
    )