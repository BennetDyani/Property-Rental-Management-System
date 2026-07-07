from __future__ import annotations

import csv
import json
import mimetypes
import re
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

_PDF_TEXT_PATTERN = re.compile(r"\((.*?)(?<!\\)\)\s*Tj", re.DOTALL)
_PDF_ARRAY_PATTERN = re.compile(r"\[(.*?)\]\s*TJ", re.DOTALL)
_PDF_ARRAY_TEXT_PATTERN = re.compile(r"\((.*?)(?<!\\)\)", re.DOTALL)


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        cleaned = _normalize_text(data)
        if cleaned:
            self._parts.append(cleaned)

    @property
    def text(self) -> str:
        return " ".join(self._parts)


@dataclass(frozen=True)
class MultimodalDocument:
    document_id: str
    source: str
    modality: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _normalize_text(text: str) -> str:
    return " ".join(text.replace("\x00", " ").split())


def _build_document(
    path: Path,
    *,
    modality: str,
    content: str,
    document_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> MultimodalDocument:
    merged_metadata = {
        "extension": path.suffix.lower(),
        "mime_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        "size_bytes": path.stat().st_size,
    }
    if metadata:
        merged_metadata.update(metadata)

    return MultimodalDocument(
        document_id=document_id or path.stem,
        source=str(path),
        modality=modality,
        content=_normalize_text(content),
        metadata=merged_metadata,
    )


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _load_json(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    return json.dumps(payload, indent=2, sort_keys=True)


def _load_csv(path: Path) -> str:
    rows: list[str] = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        reader = csv.reader(handle)
        for row in reader:
            rows.append(" | ".join(cell.strip() for cell in row if cell.strip()))
    return "\n".join(row for row in rows if row)


def _load_html(path: Path) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(path.read_text(encoding="utf-8", errors="ignore"))
    return parser.text


def _decode_pdf_string(value: str) -> str:
    return (
        value.replace(r"\(", "(")
        .replace(r"\)", ")")
        .replace(r"\n", " ")
        .replace(r"\r", " ")
        .replace(r"\t", " ")
        .replace(r"\/", "/")
        .replace(r"\\", "\\")
    )


def _load_pdf(path: Path) -> str:
    raw_text = path.read_bytes().decode("latin-1", errors="ignore")
    fragments = [_decode_pdf_string(match) for match in _PDF_TEXT_PATTERN.findall(raw_text)]

    for array_match in _PDF_ARRAY_PATTERN.findall(raw_text):
        fragments.extend(_decode_pdf_string(match) for match in _PDF_ARRAY_TEXT_PATTERN.findall(array_match))

    return "\n".join(fragment for fragment in fragments if fragment.strip())


def _load_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml_bytes = archive.read("word/document.xml")

    root = ElementTree.fromstring(xml_bytes)
    namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    fragments = [node.text or "" for node in root.findall(".//w:t", namespaces)]
    return " ".join(fragment for fragment in fragments if fragment.strip())


def _load_image(path: Path, description: str | None, metadata: dict[str, Any] | None) -> str:
    parts = [f"Image asset {path.name}"]
    if description:
        parts.append(description)
    elif metadata and metadata.get("caption"):
        parts.append(str(metadata["caption"]))
    return ". ".join(parts)


def load_document(
    path: str | Path,
    *,
    document_id: str | None = None,
    description: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> MultimodalDocument:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(file_path)

    suffix = file_path.suffix.lower()

    if suffix in {".txt", ".md", ".markdown", ".py"}:
        return _build_document(
            file_path,
            modality="text",
            content=_load_text(file_path),
            document_id=document_id,
            metadata=metadata,
        )

    if suffix == ".json":
        return _build_document(
            file_path,
            modality="text",
            content=_load_json(file_path),
            document_id=document_id,
            metadata=metadata,
        )

    if suffix == ".csv":
        return _build_document(
            file_path,
            modality="text",
            content=_load_csv(file_path),
            document_id=document_id,
            metadata=metadata,
        )

    if suffix in {".html", ".htm"}:
        return _build_document(
            file_path,
            modality="text",
            content=_load_html(file_path),
            document_id=document_id,
            metadata=metadata,
        )

    if suffix == ".pdf":
        return _build_document(
            file_path,
            modality="pdf",
            content=_load_pdf(file_path),
            document_id=document_id,
            metadata=metadata,
        )

    if suffix == ".docx":
        return _build_document(
            file_path,
            modality="word",
            content=_load_docx(file_path),
            document_id=document_id,
            metadata=metadata,
        )

    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}:
        return _build_document(
            file_path,
            modality="image",
            content=_load_image(file_path, description, metadata),
            document_id=document_id,
            metadata=metadata,
        )

    raise ValueError(f"Unsupported document type: {suffix or '<no extension>'}")


def load_documents(
    paths: list[str | Path],
    *,
    descriptions: dict[str, str] | None = None,
    metadata_by_source: dict[str, dict[str, Any]] | None = None,
) -> list[MultimodalDocument]:
    documents: list[MultimodalDocument] = []
    for path in paths:
        file_path = Path(path)
        key = str(file_path)
        documents.append(
            load_document(
                file_path,
                description=descriptions.get(key) if descriptions else None,
                metadata=metadata_by_source.get(key) if metadata_by_source else None,
            )
        )
    return documents