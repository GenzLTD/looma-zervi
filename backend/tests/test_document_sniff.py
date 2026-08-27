"""Magic-byte sniffing for resume/doc uploads."""
from src.ingest.markitdown_convert import (
    UnsupportedDocumentFormat,
    resolve_convert_filename,
    sniff_document_kind,
)


def test_sniff_docx_zip_magic():
    assert sniff_document_kind(b"PK\x03\x04" + b"rest") == "docx"


def test_sniff_legacy_doc_ole_magic():
    assert sniff_document_kind(b"\xd0\xcf\x11\xe0" + b"\x00" * 8) == "doc"


def test_sniff_pdf():
    assert sniff_document_kind(b"%PDF-1.7...") == "pdf"


def test_misnamed_docx_as_doc_rewritten():
    # ZIP magic but .doc extension → treat as .docx for MarkItDown
    name = resolve_convert_filename("简历.doc", b"PK\x03\x04xxxx")
    assert name.endswith(".docx")


def test_real_legacy_doc_rejected():
    try:
        resolve_convert_filename("余燕的中文简历.doc", b"\xd0\xcf\x11\xe0" + b"\x00" * 32)
        assert False, "expected UnsupportedDocumentFormat"
    except UnsupportedDocumentFormat as e:
        assert e.code == "legacy_doc_unsupported"
        assert ".docx" in str(e) or "PDF" in str(e)
