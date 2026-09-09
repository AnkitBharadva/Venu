"""Structured Document Parser (Docling & native engines for PDF, DOCX, PPTX)."""

import io
from typing import Any

from app.services.parsers.base import BaseParser, ParsedContent

# Conditional imports for high-speed local parsing
try:
    from pypdf import PdfReader

    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

try:
    import docx

    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    import pptx

    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False


class DoclingParser(BaseParser):
    """Parses structured documents (PDF, DOCX, PPTX) preserving hierarchical layout."""

    SUPPORTED_TYPES = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-powerpoint",
    }
    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".pptx", ".ppt"}

    def can_handle(self, content_type: str, filename: str) -> bool:
        lowered = filename.lower()
        if content_type.lower() in self.SUPPORTED_TYPES:
            return True
        return any(lowered.endswith(ext) for ext in self.SUPPORTED_EXTENSIONS)

    async def parse(self, file_bytes: bytes, filename: str, content_type: str) -> ParsedContent:
        lowered = filename.lower()

        if lowered.endswith(".pdf") or "pdf" in content_type.lower():
            return self._parse_pdf(file_bytes, filename)
        elif lowered.endswith((".docx", ".doc")) or "word" in content_type.lower():
            return self._parse_docx(file_bytes, filename)
        elif (
            lowered.endswith((".pptx", ".ppt"))
            or "presentation" in content_type.lower()
            or "powerpoint" in content_type.lower()
        ):
            return self._parse_pptx(file_bytes, filename)
        else:
            raise ValueError(f"DoclingParser cannot handle file type: {filename} ({content_type})")

    def _parse_pdf(self, file_bytes: bytes, filename: str) -> ParsedContent:
        """Parse PDF document extracting text per page and structural page bounds."""
        if not file_bytes.startswith(b"%PDF"):
            raise ValueError(f"Corrupted or invalid PDF header in '{filename}'. Expected '%PDF'.")

        if not PYPDF_AVAILABLE:
            raise RuntimeError("pypdf is required to process PDF files in offline enclave.")

        try:
            stream = io.BytesIO(file_bytes)
            reader = PdfReader(stream)
            num_pages = len(reader.pages)
            if num_pages == 0:
                raise ValueError(f"PDF '{filename}' contains 0 pages.")

            pages_data: list[dict[str, Any]] = []
            extracted_text_chunks: list[str] = []
            headings: list[dict[str, Any]] = []
            current_offset = 0

            for page_idx, page in enumerate(reader.pages, start=1):
                page_text = (page.extract_text() or "").strip()
                page_len = len(page_text)

                # Look for potential section headings (lines with short uppercase or prominent titles)
                for line in page_text.split("\n"):
                    trimmed = line.strip()
                    if 3 < len(trimmed) < 80 and (trimmed.isupper() or trimmed.istitle()):
                        headings.append(
                            {
                                "title": trimmed,
                                "page": page_idx,
                                "char_offset": current_offset + page_text.find(trimmed),
                            }
                        )

                pages_data.append(
                    {
                        "page_number": page_idx,
                        "char_start": current_offset,
                        "char_end": current_offset + page_len,
                        "char_count": page_len,
                    }
                )

                if page_text:
                    extracted_text_chunks.append(f"--- [Page {page_idx}] ---\n{page_text}")
                    current_offset += page_len + 25  # including page header offset

            combined_text = "\n\n".join(extracted_text_chunks).strip()
            total_chars = len(combined_text)

            # Check if PDF is scanned or image-only (low extracted text density)
            low_confidence = False
            confidence_score = 1.0
            warnings: list[str] = []

            if total_chars < 30 * num_pages:
                low_confidence = True
                confidence_score = 0.45
                warnings.append(
                    f"Low text density detected ({total_chars} characters across {num_pages} pages). "
                    "Document may be scanned or image-only. Recommend OCR extraction."
                )

            metadata: dict[str, Any] = {
                "parser": "DoclingPDFParser",
                "total_pages": num_pages,
                "pages": pages_data,
                "headings": headings,
                "is_encrypted": reader.is_encrypted,
                "char_count": total_chars,
            }

            return ParsedContent(
                raw_text=combined_text if combined_text else "[Scanned / Image-Only PDF: No embedded text extracted]",
                structural_metadata=metadata,
                confidence_score=confidence_score,
                low_confidence=low_confidence,
                warnings=warnings,
            )

        except Exception as exc:
            if isinstance(exc, ValueError):
                raise
            raise ValueError(f"Failed to parse corrupted PDF '{filename}': {exc}") from exc

    def _parse_docx(self, file_bytes: bytes, filename: str) -> ParsedContent:
        """Parse Microsoft Word DOCX files extracting headings and paragraph hierarchies."""
        if not file_bytes.startswith(b"PK\x03\x04"):
            raise ValueError(f"Corrupted or invalid DOCX archive in '{filename}'. Expected ZIP header.")

        if not DOCX_AVAILABLE:
            raise RuntimeError("python-docx is required to process DOCX documents.")

        try:
            stream = io.BytesIO(file_bytes)
            doc = docx.Document(stream)

            paragraphs_data: list[str] = []
            headings: list[dict[str, Any]] = []

            for p in doc.paragraphs:
                text = p.text.strip()
                if not text:
                    continue
                style_name = p.style.name if p.style else ""
                if "Heading" in style_name:
                    try:
                        level = int(style_name.replace("Heading", "").strip())
                    except ValueError:
                        level = 1
                    headings.append({"level": level, "title": text, "style": style_name})

                paragraphs_data.append(text)

            # Extract tables if present
            table_count = len(doc.tables)
            for t_idx, table in enumerate(doc.tables, start=1):
                table_lines: list[str] = []
                for row in table.rows:
                    row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                    if row_text:
                        table_lines.append(f"| {row_text} |")
                if table_lines:
                    paragraphs_data.append(f"\n[Table {t_idx}]\n" + "\n".join(table_lines))

            combined_text = "\n\n".join(paragraphs_data).strip()

            metadata: dict[str, Any] = {
                "parser": "DoclingDocxParser",
                "paragraph_count": len(doc.paragraphs),
                "table_count": table_count,
                "headings": headings,
                "char_count": len(combined_text),
                "total_pages": max(1, len(combined_text) // 2500),  # approximation for docx
            }

            return ParsedContent(
                raw_text=combined_text,
                structural_metadata=metadata,
                confidence_score=1.0,
                low_confidence=False,
                warnings=[],
            )

        except Exception as exc:
            if isinstance(exc, ValueError):
                raise
            raise ValueError(f"Failed to parse corrupted DOCX '{filename}': {exc}") from exc

    def _parse_pptx(self, file_bytes: bytes, filename: str) -> ParsedContent:
        """Parse Microsoft PowerPoint PPTX slides extracting titles, body shapes, and speaker notes."""
        if not file_bytes.startswith(b"PK\x03\x04"):
            raise ValueError(f"Corrupted or invalid PPTX archive in '{filename}'. Expected ZIP header.")

        if not PPTX_AVAILABLE:
            raise RuntimeError("python-pptx is required to process PPTX presentations.")

        try:
            stream = io.BytesIO(file_bytes)
            prs = pptx.Presentation(stream)

            slides_data: list[dict[str, Any]] = []
            extracted_sections: list[str] = []
            headings: list[dict[str, Any]] = []

            for slide_idx, slide in enumerate(prs.slides, start=1):
                slide_title = ""
                slide_texts: list[str] = []

                if slide.shapes.title and slide.shapes.title.text:
                    slide_title = slide.shapes.title.text.strip()
                    headings.append({"slide": slide_idx, "title": slide_title, "level": 1})

                for shape in slide.shapes:
                    if shape.has_text_frame and shape != slide.shapes.title:
                        shape_text = shape.text_frame.text.strip()
                        if shape_text:
                            slide_texts.append(shape_text)

                # Speaker notes
                notes_text = ""
                if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                    notes_text = slide.notes_slide.notes_text_frame.text.strip()

                slide_content_parts = []
                if slide_title:
                    slide_content_parts.append(f"## Slide {slide_idx}: {slide_title}")
                else:
                    slide_content_parts.append(f"## Slide {slide_idx}")

                if slide_texts:
                    slide_content_parts.append("\n".join(slide_texts))
                if notes_text:
                    slide_content_parts.append(f"[Speaker Notes: {notes_text}]")

                formatted_slide = "\n".join(slide_content_parts)
                extracted_sections.append(formatted_slide)

                slides_data.append(
                    {
                        "slide_number": slide_idx,
                        "title": slide_title,
                        "has_notes": bool(notes_text),
                        "shape_count": len(slide.shapes),
                    }
                )

            combined_text = "\n\n---\n\n".join(extracted_sections).strip()

            metadata: dict[str, Any] = {
                "parser": "DoclingPptxParser",
                "total_slides": len(prs.slides),
                "total_pages": len(prs.slides),
                "slides": slides_data,
                "headings": headings,
                "char_count": len(combined_text),
            }

            return ParsedContent(
                raw_text=combined_text,
                structural_metadata=metadata,
                confidence_score=1.0,
                low_confidence=False,
                warnings=[],
            )

        except Exception as exc:
            if isinstance(exc, ValueError):
                raise
            raise ValueError(f"Failed to parse corrupted PPTX '{filename}': {exc}") from exc
