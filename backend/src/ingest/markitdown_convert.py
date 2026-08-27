"""
MarkItDown: multi-format document → Markdown conversion.

Supports Word, Excel, PDF, PPT, etc. Converts binary document streams
into clean Markdown text, ready for LLM structured extraction and RAG indexing.
Scanned documents or complex table/chart layouts may produce suboptimal results;
this layer focuses on the text layer.

Migrated from Tatha project (markitdown_convert.py).

Note: MarkItDown ``[docx]`` supports modern ``.docx`` (OOXML). Legacy Word 97-2003
``.doc`` (OLE) is NOT supported without extra system tools (antiword/LibreOffice).
"""
from __future__ import annotations

import io
import os
from pathlib import Path
from typing import BinaryIO

from markitdown import MarkItDown
from markitdown._base_converter import DocumentConverterResult
from markitdown._stream_info import StreamInfo


_converter_instance: MarkItDown | None = None

# OLE Compound File (legacy .doc / .xls) vs ZIP (OOXML .docx / .xlsx) vs PDF
_OLE_MAGIC = b"\xd0\xcf\x11\xe0"
_ZIP_MAGIC = b"PK\x03\x04"
_PDF_MAGIC = b"%PDF"


class UnsupportedDocumentFormat(ValueError):
    """Raised when bytes are a known-but-unsupported binary format (e.g. legacy .doc)."""

    def __init__(self, message: str, *, code: str = "unsupported_format"):
        super().__init__(message)
        self.code = code


def sniff_document_kind(content: bytes) -> str:
    """Return coarse kind from magic bytes: docx|doc|pdf|text|unknown."""
    if not content:
        return "unknown"
    head = content[:8]
    if head.startswith(_PDF_MAGIC):
        return "pdf"
    if head.startswith(_ZIP_MAGIC):
        # OOXML packages (.docx/.xlsx/.pptx) are ZIPs
        return "docx"
    if head.startswith(_OLE_MAGIC):
        return "doc"
    # UTF-8 / UTF-16 text-ish
    sample = content[:4096]
    if b"\x00" not in sample[:200]:
        try:
            sample.decode("utf-8")
            return "text"
        except UnicodeDecodeError:
            pass
    return "unknown"


def resolve_convert_filename(filename: str | None, content: bytes) -> str:
    """
    Normalize upload filename for MarkItDown using magic bytes.

    - Misnamed ``.doc`` that is actually OOXML → treat as ``.docx``
    - Real legacy ``.doc`` (OLE) → raise UnsupportedDocumentFormat with actionable copy
    """
    name = (filename or "upload.bin").strip() or "upload.bin"
    stem, ext = os.path.splitext(name)
    ext_l = ext.lower()
    kind = sniff_document_kind(content)

    if kind == "doc":
        # Legacy Word binary — MarkItDown [docx] cannot convert this.
        raise UnsupportedDocumentFormat(
            f"「{name}」是旧版 Word（.doc）格式，当前仅支持 PDF / DOCX。"
            "请用 Word / WPS 另存为「.docx」或导出 PDF 后再上传。",
            code="legacy_doc_unsupported",
        )

    if kind == "docx" and ext_l in (".doc", "", ".bin"):
        return f"{stem or 'upload'}.docx"
    if kind == "pdf" and ext_l not in (".pdf",):
        return f"{stem or 'upload'}.pdf"

    # Extension claims .doc but magic is neither OLE nor OOXML — still guide the user.
    if ext_l == ".doc" and kind not in ("docx", "pdf", "text"):
        raise UnsupportedDocumentFormat(
            f"「{name}」无法识别为可用的 Word/PDF。"
            "请另存为 .docx 或 PDF 后重试。",
            code="legacy_doc_unsupported",
        )
    return name


def _converter() -> MarkItDown:
    """Singleton converter instance to avoid repeated initialization overhead."""
    global _converter_instance
    if _converter_instance is None:
        _converter_instance = MarkItDown()
    return _converter_instance


def convert_file(path: str | Path) -> DocumentConverterResult:
    """
    Convert a local file to Markdown.

    Args:
        path: Local file path (.pdf / .docx / .xlsx etc.)

    Returns:
        DocumentConverterResult with .markdown and .metadata fields.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return _converter().convert(str(path))


def convert_stream(
    stream: BinaryIO,
    *,
    filename: str | None = None,
    file_extension: str | None = None,
) -> DocumentConverterResult:
    """
    Convert a binary stream (e.g. uploaded file) to Markdown.

    Args:
        stream: Binary file stream (io.BytesIO or similar).
        filename: Original filename, used to infer type (e.g. "resume.pdf").
        file_extension: Known extension (e.g. ".pdf"); inferred from filename if not given.

    Returns:
        DocumentConverterResult with .markdown and .metadata fields.
    """
    ext = file_extension
    if not ext and filename:
        ext = os.path.splitext(filename)[1]
    stream_info = (
        StreamInfo(extension=ext or None, filename=filename)
        if (ext or filename)
        else None
    )
    return _converter().convert_stream(
        stream, stream_info=stream_info, file_extension=ext
    )


def file_to_markdown(path: str | Path) -> str:
    """Convenience: local file → Markdown string."""
    return convert_file(path).markdown


def stream_to_markdown(
    stream: BinaryIO,
    *,
    filename: str | None = None,
    file_extension: str | None = None,
) -> str:
    """Convenience: binary stream → Markdown string."""
    return convert_stream(
        stream, filename=filename, file_extension=file_extension
    ).markdown


def bytes_to_markdown(content: bytes, *, filename: str | None = None) -> str:
    """Upload helper: sniff format, reject legacy .doc, then convert."""
    effective = resolve_convert_filename(filename, content)
    return stream_to_markdown(io.BytesIO(content), filename=effective)
