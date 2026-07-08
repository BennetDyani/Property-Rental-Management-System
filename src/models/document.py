from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import String, Text, ForeignKey, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from src.database import Base
from src.config import settings


class Document(Base):
    """
    Represents a physical file ingested into the system.
    """
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    source_path: Mapped[str] = mapped_column(Text)
    filename: Mapped[str] = mapped_column(String(255))
    document_type: Mapped[str | None] = mapped_column(String(50))  # e.g., 'lease', 'invoice'
    modality: Mapped[str] = mapped_column(String(20))  # e.g., 'pdf', 'text', 'image'

    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id"), index=True)
    property_id: Mapped[int | None] = mapped_column(ForeignKey("properties.id"), index=True)

    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """
    Represents a small piece of a document and its vector embedding.
    """
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    chunk_id: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)

    embedding: Mapped[Vector] = mapped_column(Vector(settings.embedding_dimensions))

    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    chunk_index: Mapped[int] = mapped_column()

    document = relationship("Document", back_populates="chunks")