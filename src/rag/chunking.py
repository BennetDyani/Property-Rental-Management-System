from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.rag.document import MultimodalDocument


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    document_id: str
    source: str
    modality: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def chunk_document(
    document: MultimodalDocument,
    *,
    chunk_size: int = 120,
    chunk_overlap: int = 20,
) -> list[DocumentChunk]:
    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap cannot be negative")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    words = document.content.split()
    if not words:
        return []

    step = chunk_size - chunk_overlap
    chunks: list[DocumentChunk] = []
    for chunk_index, start in enumerate(range(0, len(words), step)):
        window = words[start : start + chunk_size]
        if not window:
            continue

        metadata = dict(document.metadata)
        metadata.update(
            {
                "chunk_index": chunk_index,
                "word_start": start,
                "word_end": start + len(window),
            }
        )

        chunks.append(
            DocumentChunk(
                chunk_id=f"{document.document_id}-chunk-{chunk_index}",
                document_id=document.document_id,
                source=document.source,
                modality=document.modality,
                text=" ".join(window),
                metadata=metadata,
            )
        )

    return chunks


def chunk_documents(
    documents: list[MultimodalDocument],
    *,
    chunk_size: int = 120,
    chunk_overlap: int = 20,
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    for document in documents:
        chunks.extend(
            chunk_document(
                document,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        )
    return chunks