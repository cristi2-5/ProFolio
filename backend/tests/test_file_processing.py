"""
File Processing Validation Tests — magic-byte sniffing for CV uploads.

Hardens validate_cv_file against extension-spoofing attacks where an
attacker renames a hostile payload (e.g. an executable) to .pdf/.docx
to bypass the prior MIME-only check.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from app.utils.file_processing import validate_cv_file


def _write(tmp_path: Path, name: str, data: bytes) -> str:
    p = tmp_path / name
    p.write_bytes(data)
    return str(p)


def test_valid_pdf_magic_passes(tmp_path: Path) -> None:
    """A file beginning with %PDF and at least one page is accepted."""
    # Smallest possible valid PDF that pypdf can parse with one (empty) page.
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000052 00000 n \n"
        b"0000000101 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\n"
        b"startxref\n149\n%%EOF\n"
    )
    path = _write(tmp_path, "resume.pdf", pdf)

    is_valid, err = validate_cv_file(path, "resume.pdf")
    assert is_valid, err


def test_pdf_extension_with_non_pdf_content_is_rejected(tmp_path: Path) -> None:
    """An EXE or random payload renamed to .pdf must be rejected pre-parse."""
    fake = b"MZ\x90\x00" + b"\x00" * 200  # PE/EXE header
    path = _write(tmp_path, "evil.pdf", fake)

    is_valid, err = validate_cv_file(path, "evil.pdf")
    assert not is_valid
    assert "PDF" in err or "magic" in err.lower()


def test_docx_zip_without_word_document_xml_is_rejected(tmp_path: Path) -> None:
    """A generic ZIP renamed to .docx must be rejected — DOCX requires word/document.xml."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("hello.txt", "not a docx")
    path = _write(tmp_path, "fake.docx", buf.getvalue())

    is_valid, err = validate_cv_file(path, "fake.docx")
    assert not is_valid
    assert "docx" in err.lower() or "word/document.xml" in err


def test_docx_with_wrong_magic_bytes_is_rejected(tmp_path: Path) -> None:
    """A .docx that doesn't even start with the ZIP signature is rejected."""
    path = _write(tmp_path, "fake.docx", b"\x00\x00\x00\x00garbage")

    is_valid, err = validate_cv_file(path, "fake.docx")
    assert not is_valid
    assert "DOCX" in err or "magic" in err.lower()


def test_empty_file_is_rejected(tmp_path: Path) -> None:
    """Empty uploads are rejected before any parsing is attempted."""
    path = _write(tmp_path, "empty.pdf", b"")

    is_valid, err = validate_cv_file(path, "empty.pdf")
    assert not is_valid
    assert "empty" in err.lower()


def test_unsupported_extension_is_rejected(tmp_path: Path) -> None:
    """Anything outside the .pdf/.docx allow-list is rejected."""
    path = _write(tmp_path, "resume.txt", b"hello world")

    is_valid, err = validate_cv_file(path, "resume.txt")
    assert not is_valid
    assert ".txt" in err
