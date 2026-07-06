from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from src.rag import (
    MultimodalDocument,
    MultimodalRetriever,
    chunk_document,
    load_document,
    load_documents,
    prepare_rag_prompt,
)


def write_docx(path: Path, text: str) -> None:
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"
        "</w:body>"
        "</w:document>"
    )

    with ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)


def test_load_document_supports_pdf_word_and_image_assets(tmp_path: Path):
    pdf_path = tmp_path / "invoice.pdf"
    pdf_path.write_bytes(
        b"%PDF-1.4\n1 0 obj\n<<>>\nstream\nBT\n/F1 12 Tf\n72 712 Td\n"
        b"(July rent received in full) Tj\nET\nendstream\nendobj\n%%EOF"
    )

    docx_path = tmp_path / "maintenance.docx"
    write_docx(docx_path, "Leaking tap in unit 4B needs approval")

    image_path = tmp_path / "inspection.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\nmock")

    pdf_document = load_document(pdf_path)
    docx_document = load_document(docx_path)
    image_document = load_document(
        image_path,
        description="Photo shows ceiling water damage in the kitchen.",
    )

    assert pdf_document.modality == "pdf"
    assert "July rent received in full" in pdf_document.content
    assert docx_document.modality == "word"
    assert "Leaking tap in unit 4B needs approval" in docx_document.content
    assert image_document.modality == "image"
    assert "ceiling water damage" in image_document.content


def test_chunk_document_splits_content_with_overlap():
    document = MultimodalDocument(
        document_id="policy",
        source="memory://policy.txt",
        modality="text",
        content=" ".join(f"word{i}" for i in range(12)),
        metadata={"category": "policy"},
    )

    chunks = chunk_document(document, chunk_size=5, chunk_overlap=2)

    assert [chunk.chunk_id for chunk in chunks] == [
        "policy-chunk-0",
        "policy-chunk-1",
        "policy-chunk-2",
        "policy-chunk-3",
    ]
    assert chunks[0].text == "word0 word1 word2 word3 word4"
    assert chunks[1].text == "word3 word4 word5 word6 word7"
    assert chunks[0].metadata["word_start"] == 0
    assert chunks[1].metadata["word_start"] == 3
    assert chunks[0].metadata["category"] == "policy"


def test_multimodal_retriever_ranks_relevant_context_and_builds_prompt(tmp_path: Path):
    lease_path = tmp_path / "lease.txt"
    lease_path.write_text(
        "Tenant may use the rooftop garden between 08:00 and 20:00.",
        encoding="utf-8",
    )

    image_path = tmp_path / "parking.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\nmock")

    documents = load_documents(
        [lease_path, image_path],
        descriptions={
            str(image_path): "Annotated image of the visitor parking bays behind the building."
        },
        metadata_by_source={
            str(lease_path): {"category": "lease"},
            str(image_path): {"category": "inspection"},
        },
    )

    retriever = MultimodalRetriever()
    retriever.add_documents(documents, chunk_size=20, chunk_overlap=5)

    results = retriever.search("Where is the visitor parking?", top_k=2)

    assert len(results) == 1
    assert results[0].chunk.modality == "image"
    assert "parking" in results[0].matched_terms

    prompt = prepare_rag_prompt("When can tenants use the rooftop garden?", retriever, top_k=2)
    assert "Question: When can tenants use the rooftop garden?" in prompt
    assert "[1]" in prompt
    assert "rooftop garden" in prompt
