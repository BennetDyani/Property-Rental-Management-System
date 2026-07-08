from __future__ import annotations

from typing import Any
from sqlalchemy import select, and_
from sqlalchemy.orm import joinedload

from src.database import SessionLocal
from src.models.document import Document, DocumentChunk
from src.rag.chunking import DocumentChunk as ChunkDTO
from src.rag.document import MultimodalDocument


class VectorStore:
    """
    Manages the persistence of documents and their embeddings in PostgreSQL using pgvector.
    """

    def save_document(
            self,
            doc: MultimodalDocument,
            chunks: list[ChunkDTO],
            embeddings: list[list[float]],
            tenant_id: int | None = None,
            property_id: int | None = None
    ) -> int:
        """
        Saves a document and its corresponding chunks with embeddings to the database.
        """
        with SessionLocal() as session:
            original_filename = str(doc.metadata.get("original_filename") or doc.source.name)
            document_type = doc.metadata.get("document_type")

            # Replace previously ingested versions of the same logical document.
            existing_query = select(Document).where(
                Document.filename == original_filename,
                Document.tenant_id == tenant_id,
                Document.property_id == property_id,
                Document.document_type == document_type,
            )
            existing_docs = session.execute(existing_query).scalars().all()
            for existing in existing_docs:
                session.delete(existing)
            session.flush()

            # 1. Create the Document record
            db_doc = Document(
                document_id=doc.document_id,
                source_path=str(doc.source),
                filename=original_filename,
                document_type=document_type,
                modality=doc.modality,
                tenant_id=tenant_id,
                property_id=property_id,
                metadata_json=doc.metadata,
            )
            session.add(db_doc)
            session.flush()  # Get the db_doc.id

            # 2. Create the Chunk records
            for chunk, embedding in zip(chunks, embeddings):
                db_chunk = DocumentChunk(
                    document_id=db_doc.id,
                    chunk_id=chunk.chunk_id,
                    content=chunk.text,
                    embedding=embedding,
                    metadata_json=chunk.metadata,
                    chunk_index=chunk.metadata.get("chunk_index", 0),
                )
                session.add(db_chunk)

            session.commit()
            return db_doc.id

    def search_similar(
            self,
            query_embedding: list[float],
            top_k: int = 5,
            filters: dict[str, Any] | None = None
    ) -> list[tuple[DocumentChunk, float]]:
        """
        Performs a cosine similarity search to find the most relevant chunks.
        """
        with SessionLocal() as session:
            # Use the L2 distance or Cosine distance provided by pgvector
            # <-> is L2 distance, <=> is cosine distance
            distance = DocumentChunk.embedding.cosine_distance(query_embedding).label("distance")
            query = select(
                DocumentChunk,
                distance
            ).join(Document, DocumentChunk.document_id == Document.id).options(joinedload(DocumentChunk.document))

            if filters:
                tenant_id = filters.get("tenant_id")
                property_id = filters.get("property_id")
                document_type = filters.get("document_type")

                if tenant_id is not None:
                    query = query.where(Document.tenant_id == tenant_id)
                if property_id is not None:
                    query = query.where(Document.property_id == property_id)
                if document_type is not None:
                    query = query.where(Document.document_type == str(document_type))

                # Basic JSON filter for metadata
                for key, value in filters.items():
                    if key in {"tenant_id", "property_id", "document_type"}:
                        continue
                    query = query.where(DocumentChunk.metadata_json[key].astext == str(value))

            query = query.order_by(distance, Document.created_at.desc()).limit(top_k)

            results = session.execute(query).all()

            # Distance is (1 - similarity), so we convert it back to a similarity score
            return [(chunk, 1.0 - float(dist)) for chunk, dist in results]

    def delete_document(self, document_id: str):
        """Removes a document and all its associated chunks."""
        with SessionLocal() as session:
            doc = session.execute(
                select(Document).where(Document.document_id == document_id)
            ).scalar_one_or_none()

            if doc:
                session.delete(doc)
                session.commit()