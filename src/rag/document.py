from __future__ import annotations

import csv
import json
import mimetypes
import re
import os
import requests
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

# Professional Document Loaders
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None


@dataclass(frozen=True)
class MultimodalDocument:
    """Represents a document with its content and metadata across different modalities."""
    document_id: str
    source: Path
    content: str
    modality: str  # 'text', 'pdf', 'word', 'image', 'json', 'csv', 'html'
    metadata: dict[str, Any] = field(default_factory=dict)


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []

    def handle_data(self, data):
        self.text_parts.append(data)

    def get_text(self) -> str:
        return " ".join(self.text_parts).strip()


def _call_orpheus_ocr(path: Path) -> str | None:
    """
    Sends an image or PDF to the Orpheus Vision API for high-accuracy
    OCR and image recognition.
    """
    api_key = os.getenv("ORPHEUS_API_KEY")
    if not api_key:
        return None

    try:
        with open(path, "rb") as f:
            files = {"file": f}
            headers = {"Authorization": f"Bearer {api_key}"}
            # Using the recommended Orpheus multimodal endpoint
            response = requests.post(
                "https://api.orpheus.ai/v1/recognize",
                headers=headers,
                files=files,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            # Extract the primary text or description from Orpheus response
            return data.get("text") or data.get("description")
    except Exception as e:
        print(f"Orpheus OCR Error for {path.name}: {e}")
        return None


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").strip()


def _load_json(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return json.dumps(data, indent=2)


def _load_csv(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = [" | ".join(row) for row in reader]
        return "\n".join(rows)


def _load_html(path: Path) -> str:
    content = path.read_text(encoding="utf-8", errors="replace")
    parser = _HTMLTextExtractor()
    parser.feed(content)
    return parser.get_text()


def _load_pdf(path: Path) -> str:
    if PdfReader is None:
        return "[Error: pypdf not installed. Cannot read PDF.]"

    try:
        reader = PdfReader(path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        return f"[Error reading PDF {path.name}: {e}]"


def _load_docx(path: Path) -> str:
    if DocxDocument is None:
        return "[Error: python-docx not installed. Cannot read DOCX.]"

    try:
        doc = DocxDocument(path)
        return "\n".join([para.text for para in doc.paragraphs]).strip()
    except Exception as e:
        return f"[Error reading DOCX {path.name}: {e}]"


def _load_image(path: Path, description: str | None, metadata: dict[str, Any] | None) -> str:
    parts = [f"Image asset {path.name}"]

    # 1. Try Orpheus Professional Recognition first
    orpheus_text = _call_orpheus_ocr(path)
    if orpheus_text:
        parts.append(f"Orpheus Recognition: {orpheus_text}")

    # 2. Fallback to provided descriptions/captions
    if description:
        parts.append(description)
    elif metadata and metadata.get("caption"):
        parts.append(str(metadata["caption"]))

    return ". ".join(parts)


def load_document(
        path: Path | str,
        description: str | None = None,
        metadata: dict[str, Any] | None = None
) -> MultimodalDocument:
    """Loads a single file and returns a MultimodalDocument."""
    path = Path(path)
    ext = path.suffix.lower()

    # Initialize metadata
    doc_metadata = metadata.copy() if metadata else {}
    doc_metadata.update({
        "extension": ext,
        "mime_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        "size_bytes": path.stat().st_size if path.exists() else 0,
    })

    # Route based on extension
    if ext in [".txt", ".md", ".markdown", ".py"]:
        content = _load_text(path)
        modality = "text"
    elif ext == ".json":
        content = _load_json(path)
        modality = "json"
    elif ext == ".csv":
        content = _load_csv(path)
        modality = "csv"
    elif ext in [".html", ".htm"]:
        content = _load_html(path)
        modality = "html"
    elif ext == ".pdf":
        content = _load_pdf(path)
        modality = "pdf"
    elif ext == ".docx":
        content = _load_docx(path)
        modality = "word"
    elif ext in [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"]:
        content = _load_image(path, description, doc_metadata)
        modality = "image"
    else:
        # Fallback for unknown types
        try:
            content = _load_text(path)
            modality = "text"
        except Exception:
            content = f"[Unsupported file format: {ext}]"
            modality = "unknown"

    return MultimodalDocument(
        document_id=str(doc_metadata.get("document_id") or path.stem),
        source=path,
        content=content,
        modality=modality,
        metadata=doc_metadata
    )


def load_documents(
        paths: list[Path | str],
        descriptions: dict[str, str] | None = None,
        metadata_by_source: dict[str, dict[str, Any]] | None = None
) -> list[MultimodalDocument]:
    """Loads multiple files into MultimodalDocument objects."""
    documents = []
    for p in paths:
        path = Path(p)
        key = str(path)

        desc = descriptions.get(key) if descriptions else None
        meta = metadata_by_source.get(key) if metadata_by_source else None

        documents.append(load_document(path, description=desc, metadata=meta))

    return documents