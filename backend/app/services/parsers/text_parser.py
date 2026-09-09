"""Plain text and Markdown parser for normalized ingestion."""

import re
from typing import Any

from app.services.parsers.base import BaseParser, ParsedContent


class TextParser(BaseParser):
    """Parser for UTF-8 and ASCII plain text, Markdown, and structured text formats."""

    SUPPORTED_TYPES = {
        "text/plain",
        "text/markdown",
        "text/x-markdown",
        "text/csv",
        "application/json",
        "text/tab-separated-values",
    }
    SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".json", ".log"}

    def can_handle(self, content_type: str, filename: str) -> bool:
        lowered_name = filename.lower()
        if content_type.lower() in self.SUPPORTED_TYPES:
            return True
        return any(lowered_name.endswith(ext) for ext in self.SUPPORTED_EXTENSIONS)

    async def parse(self, file_bytes: bytes, filename: str, content_type: str) -> ParsedContent:
        if not file_bytes or len(file_bytes.strip()) == 0:
            raise ValueError(f"File '{filename}' is completely empty.")

        # Decode with fallback for common character encodings
        text = ""
        for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                text = file_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        if not text:
            raise ValueError(f"Failed to decode text file '{filename}' with supported encodings.")

        # Normalize carriage returns
        normalized_text = text.replace("\r\n", "\n").replace("\r", "\n").strip()

        # Extract Markdown headings if present
        headings: list[dict[str, Any]] = []
        for line_num, line in enumerate(normalized_text.split("\n"), start=1):
            match = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
            if match:
                level = len(match.group(1))
                title = match.group(2).strip()
                headings.append({"level": level, "title": title, "line": line_num})

        paragraphs = [p.strip() for p in normalized_text.split("\n\n") if p.strip()]
        words = normalized_text.split()

        metadata: dict[str, Any] = {
            "parser": "TextParser",
            "format": "markdown" if filename.lower().endswith((".md", ".markdown")) else "plain_text",
            "char_count": len(normalized_text),
            "word_count": len(words),
            "paragraph_count": len(paragraphs),
            "headings": headings,
            "total_pages": 1,
        }

        return ParsedContent(
            raw_text=normalized_text,
            structural_metadata=metadata,
            confidence_score=1.0,
            low_confidence=False,
            warnings=[],
        )
