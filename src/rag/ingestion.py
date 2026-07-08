from __future__ import annotations

from pathlib import Path
from typing import Any
from langchain_ollama import OllamaEmbeddings

from src.rag.chunking import DocumentChunk, chunk_documents
from src.rag.document import MultimodalDocument, load_documents
from src.rag.retriever import MultimodalRetriever
from src.rag.vector_store import VectorStore


class DocumentIngestor:
    """
    Handles the pipeline of loading raw files, generating embeddings,
    and persisting them in the VectorStore.
    """

    def __init__(
            self,
            retriever: MultimodalRetriever,
            vector_store: VectorStore,
            embedding_model_name: str = "nomic-embed-text",
            ollama_base_url: str = "http://localhost:11434"
    ):
        self.retriever = retriever
        self.vector_store = vector_store
        self.embedder = OllamaEmbeddings(
            model=embedding_model_name,
            base_url=ollama_base_url
        )

    def ingest_files(
            self,
            file_paths: list[str | Path],
            descriptions: dict[str, str] | None = None,
            metadata_by_source: dict[str, dict[str, Any]] | None = None,
            tenant_id: int | None = None,
            property_id: int | None = None
    ) -> list[DocumentChunk]:
        """
        Full Pipeline: Load -> Chunk -> Embed -> Persist in DB -> Update Retriever.
        """
        # 1. Load raw files
        documents = load_documents(
            file_paths,
            descriptions=descriptions,
            metadata_by_source=metadata_by_source
        )

        # 2. Chunk the documents
        all_chunks = chunk_documents(documents)

        # 3. Embed and Persist each document
        for doc in documents:
            # Filter chunks belonging to this specific document
            doc_chunks = [c for c in all_chunks if c.document_id == doc.document_id]

            # Generate embeddings for these chunks
            texts = [c.text for c in doc_chunks]
            embeddings = self.embedder.embed_documents(texts)

            # Save to PostgreSQL via VectorStore
            self.vector_store.save_document(
                doc=doc,
                chunks=doc_chunks,
                embeddings=embeddings,
                tenant_id=tenant_id,
                property_id=property_id
            )

        # 4. Update the in-memory retriever for immediate availability
        self.retriever.add_chunks(all_chunks)

        return all_chunks

    def ingest_directory(
            self,
            directory_path: str | Path,
            metadata_filter: dict[str, Any] | None = None,
            tenant_id: int | None = None,
            property_id: int | None = None,
            extensions: list[str] | None = None
    ) -> list[DocumentChunk]:
        """Scans a directory and persists all supported files."""
        dir_path = Path(directory_path)
        if not dir_path.is_dir():
            raise FileNotFoundError(f"Directory not found: {directory_path}")

        if extensions is None:
            extensions = [".txt", ".md", ".pdf", ".docx", ".csv", ".json", ".png", ".jpg", ".jpeg", ".webp"]

        files = [f for f in dir_path.iterdir() if f.is_file() and f.suffix.lower() in extensions]

        metadata_map = {}
        for f in files:
            meta = metadata_filter.copy() if metadata_filter else {}
            meta["folder"] = dir_path.name
            metadata_map[str(f)] = meta

        return self.ingest_files(
            file_paths=files,
            metadata_by_source=metadata_map,
            tenant_id=tenant_id,
            property_id=property_id
        )