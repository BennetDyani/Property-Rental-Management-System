from __future__ import annotations

import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from src.database import init_database
from src.rag.retriever import MultimodalRetriever
from src.rag.vector_store import VectorStore
from src.rag.ingestion import DocumentIngestor
from src.agents.orchestrator import PropertyOrchestrator

load_dotenv()

# Initialize App
app = FastAPI(title="AI Property Rental Management API")

# --- Global State (Singletons) ---
# We initialize these once at startup to avoid reloading models every request
state = {}


def _build_document_key(
    filename: str,
    tenant_id: Optional[int],
    property_id: Optional[int],
    doc_type: Optional[str],
) -> str:
    """Build a stable ID so re-uploads of the same logical document replace old versions."""
    stem = Path(filename).stem
    safe_stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", stem).strip("_").lower() or "document"
    tenant_part = f"tenant-{tenant_id}" if tenant_id is not None else "tenant-any"
    property_part = f"property-{property_id}" if property_id is not None else "property-any"
    type_part = re.sub(r"[^a-zA-Z0-9_-]+", "_", (doc_type or "general")).strip("_").lower() or "general"
    return f"{tenant_part}__{property_part}__{type_part}__{safe_stem}"


@app.on_event("startup")
async def startup_event():
    # 1. Init DB
    init_database()

    # 2. Init RAG components
    vector_store = VectorStore()
    retriever = MultimodalRetriever(vector_store=vector_store)

    # 3. Init Ingestion pipeline
    ingestor = DocumentIngestor(retriever=retriever, vector_store=vector_store)

    # 4. Init Orchestrator (The Brain)
    orchestrator = PropertyOrchestrator(retriever=retriever)

    state["orchestrator"] = orchestrator
    state["ingestor"] = ingestor


# --- Request/Response Schemas ---
class ChatRequest(BaseModel):
    message: str
    thread_id: str
    tenant_id: Optional[int] = None
    unit_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    thread_id: str


class IngestResponse(BaseModel):
    status: str
    message: str
    document_id: Optional[str] = None


# --- Endpoints ---

@app.get("/health")
async def health_check():
    """Check if the API and Database are online."""
    return {"status": "online", "version": "1.0.0"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main entry point for AI interaction.
    n8n calls this when a message is received via WhatsApp/Email.
    """
    try:
        orchestrator = state["orchestrator"]
        response = orchestrator.run(
            query=request.message,
            thread_id=request.thread_id,
            tenant_id=request.tenant_id
        )
        return ChatResponse(response=response, thread_id=request.thread_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    file: UploadFile = File(...),
    tenant_id: Optional[int] = Form(None),
    property_id: Optional[int] = Form(None),
    doc_type: Optional[str] = Form("general")
):
    """
    Upload a document (PDF, Image, Docx) and ingest it into the RAG system.
    n8n calls this when a document is uploaded.
    """
    try:
        # 1. Save uploaded file to a temporary location
        upload_dir = Path("temp_uploads")
        upload_dir.mkdir(exist_ok=True)

        file_ext = Path(file.filename).suffix
        temp_filename = f"{uuid.uuid4()}{file_ext}"
        temp_path = upload_dir / temp_filename

        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 2. Run the ingestion pipeline
        ingestor = state["ingestor"]
        metadata = {
            "document_type": doc_type,
            "original_filename": file.filename,
            "document_id": _build_document_key(
                filename=file.filename,
                tenant_id=tenant_id,
                property_id=property_id,
                doc_type=doc_type,
            ),
        }

        # Process the file
        chunks = ingestor.ingest_files(
            file_paths=[temp_path],
            metadata_by_source={str(temp_path): metadata},
            tenant_id=tenant_id,
            property_id=property_id
        )

        # 3. Cleanup temp file
        temp_path.unlink()

        return IngestResponse(
            status="success",
            message=f"Successfully ingested {file.filename}. Created {len(chunks)} chunks.",
            document_id=chunks[0].document_id if chunks else None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    print("\n🚀 Starting AI Property Backend on http://localhost:8000")
    print("Press Ctrl+C to stop the server\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)