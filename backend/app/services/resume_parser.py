"""PDF/DOCX text extraction. Scanned/image-only PDFs are unsupported (no OCR in v1)."""

from __future__ import annotations

import re


class ParseError(Exception):
    def __init__(self, message: str, code: str = "unreadable_file"):
        super().__init__(message)
        self.code = code


def normalize_extracted_text(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    collapsed: list[str] = []
    blank = False
    for line in lines:
        if not line:
            if not blank and collapsed:
                collapsed.append("")
            blank = True
        else:
            collapsed.append(line)
            blank = False
    return "\n".join(collapsed).strip()


def extract_pdf_text(path: str) -> str:
    try:
        import pdfplumber
    except ImportError as exc:
        raise ParseError("PDF support is not installed (pdfplumber).") from exc

    try:
        with pdfplumber.open(path) as pdf:
            if getattr(pdf, "is_encrypted", False):
                raise ParseError(
                    "This PDF is encrypted or password-protected and cannot be read.",
                    code="encrypted_pdf",
                )
            parts = []
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
            return normalize_extracted_text("\n".join(parts))
    except ParseError:
        raise
    except Exception as exc:
        message = str(exc).lower()
        if "password" in message or "encrypt" in message:
            raise ParseError(
                "This PDF is encrypted or password-protected and cannot be read.",
                code="encrypted_pdf",
            ) from exc
        raise ParseError(
            "The PDF could not be parsed. Corrupt or scanned PDFs are not supported in v1.",
            code="unreadable_file",
        ) from exc


def extract_docx_text(path: str) -> str:
    try:
        import docx2txt
    except ImportError as exc:
        raise ParseError("DOCX support is not installed (docx2txt).") from exc
    try:
        text = docx2txt.process(path) or ""
    except Exception as exc:
        raise ParseError("The DOCX file could not be parsed.", code="unreadable_file") from exc
    return normalize_extracted_text(text)


def parse_resume_file(path: str, file_type: str) -> str:
    if file_type == "pdf":
        text = extract_pdf_text(path)
    elif file_type == "docx":
        text = extract_docx_text(path)
    else:
        raise ParseError("Only PDF and DOCX files are supported.", code="unsupported_file_type")
    if not text:
        raise ParseError(
            "No extractable text was found. Image-only/scanned PDFs are not supported in v1 (OCR is a future enhancement).",
            code="empty_text",
        )
    return text
