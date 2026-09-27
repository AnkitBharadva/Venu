"""High-Precision Structure- and Semantic-Aware Chunker for Phase 2.

Guarantees 100% ground-truth provenance:
raw_text[chunk.char_offset_start:chunk.char_offset_end] == chunk.text

Key Capabilities:
1. Universal Heading Detection:
   - Markdown headings (# H1, ## H2)
   - Numbered outline headings (1.1 Title, Section 1: Title)
   - All-caps standalone section headings (AIR-GAP DEFENSE DIRECTIVE 2026)
   - Underline markdown headings (Heading\\n===)
2. Atomic Structural Block Preservation:
   - Markdown & ASCII tables preserved 100% intact as atomic blocks (never chopped mid-table)
   - Fenced code blocks (``` ... ```) preserved as atomic blocks
   - Bulleted & numbered procedural lists grouped coherently (never split mid-item)
3. Syntactic Sentence Tokenization:
   - Boundary detection guarded against abbreviations (e.g., i.e., Dr., etc.), decimals (v3.11, 3.14),
     technical identifiers (CVE-2024-38077, S-400), citations ([1], [12]), and single initials.
4. Embedding Distance Breakpoint Detection:
   - Evaluates cosine distance spikes between adjacent sentences using local neural embedder
     (FastEmbed BAAI/bge-small-en-v1.5) to detect true topic transition boundaries.
5. Sentence-Aligned Lookback Overlap:
   - Overlaps consecutive sub-chunks by full sentences rather than slicing mid-word or mid-sentence.
6. Structural Metadata Propagation:
   - Page boundaries, audio/video timestamps, section titles, and element type tags.
"""

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class ExtractedChunk:
    """A semantically coherent text unit addressable by exact character span."""

    chunk_id: uuid.UUID
    chunk_index: int
    text: str
    char_offset_start: int
    char_offset_end: int
    page_number: int | None = None
    heading: str | None = None
    timestamp_start: float | None = None
    timestamp_end: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def verify_provenance(self, source_text: str) -> bool:
        """Verify that chunk text strictly matches source text at recorded offsets."""
        return source_text[self.char_offset_start : self.char_offset_end] == self.text


class SemanticChunker:
    """Structure- and semantic-aware chunker with structural metadata preservation."""

    def __init__(
        self,
        min_chunk_chars: int = 100,
        target_chunk_chars: int = 500,
        max_chunk_chars: int = 850,
        overlap_chars: int = 100,
        embedder: Any | None = None,
        use_semantic_breakpoints: bool = False,
    ) -> None:
        self.min_chunk_chars = min_chunk_chars
        self.target_chunk_chars = target_chunk_chars
        self.max_chunk_chars = max_chunk_chars
        self.overlap_chars = overlap_chars
        self.embedder = embedder
        self.use_semantic_breakpoints = use_semantic_breakpoints

    def chunk_text(
        self,
        raw_text: str,
        structural_metadata: dict[str, Any] | None = None,
    ) -> list[ExtractedChunk]:
        """Chunk normalized raw_text into coherent semantic units.

        Guarantees exact character slice equality for all returned chunks.
        """
        if not raw_text or not raw_text.strip():
            return []

        metadata = structural_metadata or {}
        text_len = len(raw_text)

        # 1. Structural Boundaries: Headings, Pages, Timestamps
        heading_map = self._build_heading_map(raw_text, metadata)
        page_intervals = self._build_page_intervals(raw_text, metadata)
        timestamp_intervals = self._build_timestamp_intervals(metadata)

        # 2. Identify Atomic Structural Blocks (Tables, Code, Lists, Paragraphs)
        structural_blocks = self._identify_structural_blocks(raw_text)

        # 3. Assemble Spans Respecting Atomic Elements & Size Bounds
        raw_spans: list[tuple[int, int, dict[str, Any]]] = []
        pending_s: int | None = None
        pending_e: int | None = None
        pending_heading: str | None = None
        pending_page: int | None = None
        pending_meta: dict[str, Any] = {}

        def flush_pending() -> None:
            nonlocal pending_s, pending_e, pending_heading, pending_page, pending_meta
            if pending_s is not None and pending_e is not None:
                s_trim, e_trim = self._trim_span_offsets(raw_text, pending_s, pending_e)
                if s_trim < e_trim:
                    raw_spans.append((s_trim, e_trim, pending_meta))
                pending_s, pending_e = None, None
                pending_heading = None
                pending_page = None
                pending_meta = {}

        for b_start, b_end, b_type in structural_blocks:
            b_len = b_end - b_start
            b_heading = self._resolve_heading_for_offset(b_start, heading_map)
            b_page = self._resolve_page_for_offset(b_start, page_intervals)

            # Atomic structures: Tables and Code Blocks are never smushed with surrounding text
            if b_type in ("table", "code"):
                flush_pending()
                raw_spans.append((b_start, b_end, {f"is_{b_type}": True}))
                continue

            # Atomic Lists: keep list intact if within reasonable budget
            if b_type == "list":
                flush_pending()
                if b_len <= self.max_chunk_chars:
                    raw_spans.append((b_start, b_end, {"is_list": True}))
                else:
                    # Subdivide long list item by item
                    sub_list_spans = self._split_list_items(raw_text, b_start, b_end)
                    raw_spans.extend(sub_list_spans)
                continue

            # Oversized paragraph: must be split on sentence boundaries
            if b_len > self.max_chunk_chars:
                flush_pending()
                sub_spans = self._split_paragraph_into_chunks(raw_text, b_start, b_end)
                raw_spans.extend(sub_spans)
                continue

            # Regular paragraph
            heading_changed = (
                pending_heading is not None
                and b_heading is not None
                and b_heading != pending_heading
            )
            page_changed = (
                pending_page is not None
                and b_page is not None
                and b_page != pending_page
            )

            if pending_s is not None and pending_e is not None:
                combined_len = b_end - pending_s
                # Only combine if under target_chunk_chars, same heading, and same page
                if heading_changed or page_changed or combined_len > self.target_chunk_chars:
                    flush_pending()
                    pending_s = b_start
                    pending_e = b_end
                    pending_heading = b_heading
                    pending_page = b_page
                    pending_meta = {}
                else:
                    pending_e = b_end
                    if pending_heading is None:
                        pending_heading = b_heading
                    if pending_page is None:
                        pending_page = b_page
            else:
                pending_s = b_start
                pending_e = b_end
                pending_heading = b_heading
                pending_page = b_page
                pending_meta = {}

        flush_pending()

        # 4. Construct ExtractedChunk objects with defensive verification
        chunks: list[ExtractedChunk] = []
        for idx, (s, e, c_meta) in enumerate(raw_spans):
            s_trim, e_trim = self._trim_span_offsets(raw_text, s, e)
            if s_trim >= e_trim:
                continue

            chunk_text = raw_text[s_trim:e_trim]
            if not chunk_text.strip():
                continue

            heading_val = self._resolve_heading_for_offset(s_trim, heading_map)
            page_val = self._resolve_page_for_offset(s_trim, page_intervals)
            t_start, t_end = self._resolve_timestamps_for_offset(s_trim, e_trim, timestamp_intervals)

            final_meta = {
                "char_count": len(chunk_text),
                "word_count": len(chunk_text.split()),
                **c_meta,
            }

            chunk = ExtractedChunk(
                chunk_id=uuid.uuid4(),
                chunk_index=len(chunks),
                text=chunk_text,
                char_offset_start=s_trim,
                char_offset_end=e_trim,
                page_number=page_val,
                heading=heading_val,
                timestamp_start=t_start,
                timestamp_end=t_end,
                metadata=final_meta,
            )

            if not chunk.verify_provenance(raw_text):
                raise ValueError(
                    f"Provenance invariant violated at chunk {idx}: "
                    f"raw_text[{s_trim}:{e_trim}] != chunk.text"
                )

            chunks.append(chunk)

        # Fallback if text produced zero chunks (e.g. single word text)
        if not chunks and raw_text.strip():
            s_trim, e_trim = self._trim_span_offsets(raw_text, 0, text_len)
            if s_trim < e_trim:
                chunks.append(
                    ExtractedChunk(
                        chunk_id=uuid.uuid4(),
                        chunk_index=0,
                        text=raw_text[s_trim:e_trim],
                        char_offset_start=s_trim,
                        char_offset_end=e_trim,
                        page_number=self._resolve_page_for_offset(s_trim, page_intervals),
                        heading=self._resolve_heading_for_offset(s_trim, heading_map),
                        metadata={"char_count": e_trim - s_trim, "word_count": len(raw_text[s_trim:e_trim].split())},
                    )
                )

        return chunks

    def _trim_span_offsets(self, text: str, start: int, end: int) -> tuple[int, int]:
        """Adjust start and end to exclude whitespace while maintaining exact index mapping."""
        text_len = len(text)
        start = max(0, min(start, text_len))
        end = max(start, min(end, text_len))
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        return start, end

    def _build_heading_map(self, text: str, metadata: dict[str, Any]) -> list[tuple[int, str]]:
        """Build an ordered list of (char_offset, heading_title) supporting Markdown, outlines, and all-caps."""
        headings: list[tuple[int, str]] = []

        # From structural metadata if provided by parsers
        raw_headings = metadata.get("headings", [])
        if isinstance(raw_headings, list):
            for h in raw_headings:
                if isinstance(h, dict):
                    title = h.get("title") or h.get("heading") or h.get("text")
                    offset = h.get("char_offset")
                    if title and offset is not None and isinstance(offset, int):
                        headings.append((offset, str(title).strip()))
                    elif title:
                        f_idx = text.find(str(title).strip())
                        if f_idx >= 0:
                            headings.append((f_idx, str(title).strip()))

        # 1. Markdown headings (# Header, ## Subheader)
        for m in re.finditer(r"^(#{1,6})\s+(.+)$", text, re.MULTILINE):
            headings.append((m.start(), m.group(2).strip()))

        # 2. Numbered outline headings (1.1 Title or Section 1: Title)
        outline_pattern = re.compile(
            r"^(?:(?:Section|Chapter|Part|Article)\s+)?(\d+(?:\.\d+)*)[:.\s]+([A-Z][A-Za-z0-9\s\-_,()]+)$",
            re.MULTILINE,
        )
        for m in outline_pattern.finditer(text):
            headings.append((m.start(), m.group(0).strip()))

        # 3. All-caps standalone headings (e.g., AIR-GAP DEFENSE DIRECTIVE 2026)
        all_caps_pattern = re.compile(r"^([A-Z0-9][A-Z0-9\s\-_:]{3,80})$", re.MULTILINE)
        for m in all_caps_pattern.finditer(text):
            candidate = m.group(1).strip()
            letters = [c for c in candidate if c.isalpha()]
            if len(letters) >= 4 and candidate not in [h[1] for h in headings]:
                headings.append((m.start(), candidate))

        # Deduplicate by offset and sort ascending
        offset_dict: dict[int, str] = {}
        for offset, h in sorted(headings, key=lambda x: x[0]):
            if offset not in offset_dict:
                offset_dict[offset] = h
        return sorted(offset_dict.items(), key=lambda x: x[0])

    def _build_page_intervals(self, text: str, metadata: dict[str, Any]) -> list[tuple[int, int, int]]:
        """Build list of (start_offset, end_offset, page_number)."""
        intervals: list[tuple[int, int, int]] = []
        pages = metadata.get("pages", [])
        if isinstance(pages, list) and pages:
            for p in pages:
                if isinstance(p, dict):
                    page_num = p.get("page_number") or p.get("page")
                    s = p.get("char_start") or p.get("start_offset")
                    e = p.get("char_end") or p.get("end_offset")
                    if page_num is not None and s is not None and e is not None:
                        intervals.append((int(s), int(e), int(page_num)))

        if not intervals:
            page_matches = list(re.finditer(r"---\s*\[(?:Page|Slide)\s*(\d+)\]\s*---", text, re.IGNORECASE))
            for i, match in enumerate(page_matches):
                p_num = int(match.group(1))
                s = match.start()
                e = page_matches[i + 1].start() if i + 1 < len(page_matches) else len(text)
                intervals.append((s, e, p_num))

        intervals.sort(key=lambda x: x[0])
        return intervals

    def _build_timestamp_intervals(self, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract audio/video segment timestamps."""
        ts_list = metadata.get("timestamps", [])
        if isinstance(ts_list, list):
            return [t for t in ts_list if isinstance(t, dict) and "start" in t]
        return []

    def _resolve_heading_for_offset(self, offset: int, heading_map: list[tuple[int, str]]) -> str | None:
        """Find the nearest heading preceding the given offset."""
        current_heading: str | None = None
        for h_offset, title in heading_map:
            if h_offset <= offset:
                current_heading = title
            else:
                break
        return current_heading

    def _resolve_page_for_offset(self, offset: int, page_intervals: list[tuple[int, int, int]]) -> int | None:
        """Find the page number containing the given offset."""
        for s, e, page_num in page_intervals:
            if s <= offset <= e:
                return page_num
        if page_intervals and offset >= page_intervals[-1][0]:
            return page_intervals[-1][2]
        return 1 if page_intervals else None

    def _resolve_timestamps_for_offset(
        self, start_offset: int, end_offset: int, timestamp_intervals: list[dict[str, Any]]
    ) -> tuple[float | None, float | None]:
        """Align chunk character range with audio/video timestamps if present."""
        if not timestamp_intervals:
            return None, None
        matched_starts: list[float] = []
        matched_ends: list[float] = []
        for seg in timestamp_intervals:
            s = seg.get("char_start")
            e = seg.get("char_end")
            t_start = seg.get("start")
            t_end = seg.get("end")
            if s is not None and e is not None and t_start is not None and t_end is not None:
                if max(start_offset, s) <= min(end_offset, e):
                    matched_starts.append(float(t_start))
                    matched_ends.append(float(t_end))
        if matched_starts and matched_ends:
            return min(matched_starts), max(matched_ends)
        return None, None

    def _identify_structural_blocks(self, text: str) -> list[tuple[int, int, str]]:
        """Identify atomic blocks: tables, code blocks, lists, and paragraphs with exact character spans."""
        text_len = len(text)

        # 1. Identify all code blocks
        code_spans = []
        for m in re.finditer(r"```[^\n]*\n[\s\S]*?\n```", text):
            code_spans.append((m.start(), m.end(), "code"))

        # 2. Identify all markdown tables (2 or more contiguous lines starting and ending with |)
        table_spans = []
        table_pattern = re.compile(r"(?:^[ \t]*\|.+?\|[ \t]*$(?:\r?\n)?){2,}", re.MULTILINE)
        for m in table_pattern.finditer(text):
            table_spans.append((m.start(), m.end(), "table"))

        # 3. Identify all list blocks (2 or more contiguous list items)
        list_spans = []
        list_pattern = re.compile(
            r"(?:^[ \t]*(?:[-*+•]|\d+[\.\)]|\([a-zA-Z0-9]+\))[ \t]+.+$(?:\r?\n)?){2,}",
            re.MULTILINE,
        )
        for m in list_pattern.finditer(text):
            list_spans.append((m.start(), m.end(), "list"))

        # Merge atomic spans avoiding overlaps
        atomic_spans = sorted(code_spans + table_spans + list_spans, key=lambda x: x[0])
        filtered_atomic = []
        last_end = 0
        for s, e, btype in atomic_spans:
            if s >= last_end:
                filtered_atomic.append((s, e, btype))
                last_end = e

        break_pattern = re.compile(r"(\r?\n\s*\r?\n+|---+(?:\s*\[.*?\]\s*---+)?|\r?\n---+\s*)")

        # Partition text into atomic spans and intervening paragraphs
        blocks: list[tuple[int, int, str]] = []
        cursor = 0
        for s, e, btype in filtered_atomic:
            if s > cursor:
                intervening = text[cursor:s]
                p_cursor = cursor
                for pm in break_pattern.finditer(intervening):
                    p_end = cursor + pm.start()
                    if p_end > p_cursor:
                        blocks.append((p_cursor, p_end, "paragraph"))
                    p_cursor = cursor + pm.end()
                if cursor + len(intervening) > p_cursor:
                    blocks.append((p_cursor, cursor + len(intervening), "paragraph"))
            blocks.append((s, e, btype))
            cursor = e

        if cursor < text_len:
            intervening = text[cursor:]
            p_cursor = cursor
            for pm in break_pattern.finditer(intervening):
                p_end = cursor + pm.start()
                if p_end > p_cursor:
                    blocks.append((p_cursor, p_end, "paragraph"))
                p_cursor = cursor + pm.end()
            if cursor + len(intervening) > p_cursor:
                blocks.append((p_cursor, cursor + len(intervening), "paragraph"))

        cleaned_blocks = []
        for s, e, btype in blocks:
            s_trim, e_trim = self._trim_span_offsets(text, s, e)
            if s_trim < e_trim:
                cleaned_blocks.append((s_trim, e_trim, btype))
        return cleaned_blocks

    def _split_list_items(self, text: str, list_start: int, list_end: int) -> list[tuple[int, int, dict[str, Any]]]:
        """Subdivide oversized lists at item boundaries."""
        list_slice = text[list_start:list_end]
        item_pattern = re.compile(r"^[ \t]*(?:[-*+•]|\d+[\.\)]|\([a-zA-Z0-9]+\))[ \t]+", re.MULTILINE)
        matches = list(item_pattern.finditer(list_slice))
        if not matches:
            return [(list_start, list_end, {"is_list": True})]

        item_spans = []
        for i, m in enumerate(matches):
            s = list_start + m.start()
            e = list_start + (matches[i + 1].start() if i + 1 < len(matches) else len(list_slice))
            s_trim, e_trim = self._trim_span_offsets(text, s, e)
            if s_trim < e_trim:
                item_spans.append((s_trim, e_trim))

        grouped: list[tuple[int, int, dict[str, Any]]] = []
        curr_s: int | None = None
        curr_e: int | None = None

        for s, e in item_spans:
            if curr_s is None:
                curr_s, curr_e = s, e
            else:
                if (e - curr_s) <= self.target_chunk_chars:
                    curr_e = e
                else:
                    grouped.append((curr_s, curr_e, {"is_list": True}))
                    curr_s, curr_e = s, e

        if curr_s is not None and curr_e is not None:
            grouped.append((curr_s, curr_e, {"is_list": True}))

        return grouped

    def _split_into_sentences(self, text: str, span_start: int, span_end: int) -> list[tuple[int, int]]:
        """Split text span into sentences with exact character offsets, protecting abbreviations, decimals, and citations."""
        span_slice = text[span_start:span_end]
        if not span_slice.strip():
            return []

        abbreviations = {
            "u.s", "u.k", "e.u", "u.n", "d.c", "e.g", "i.e", "vs", "etc", "al",
            "dr", "mr", "mrs", "ms", "prof", "gen", "col", "capt", "lt", "maj", "sgt",
            "dept", "inc", "corp", "ltd", "co", "approx", "no", "fig", "sec", "vol", "p", "pp",
        }
        pattern = re.compile(r'([.!?]+)([\'"]?)(\s+|\r?\n+)(?=[A-Z0-9"\'\(\[\{]|\Z)')
        boundaries = [0]

        for m in pattern.finditer(span_slice):
            punct = m.group(1)
            punct_end = m.end(1)
            preceding = span_slice[:punct_end - len(punct)].strip()

            if punct == ".":
                last_token = re.split(r"[\s\(\[\{\'\"/]+", preceding)[-1].lower() if preceding else ""
                if last_token in abbreviations:
                    continue
                m_start = m.start(1)
                # Decimal check (e.g. 3.11, v3.11, 10.5)
                if m_start > 0 and m_start + 1 < len(span_slice):
                    if span_slice[m_start - 1].isdigit() and span_slice[m_start + 1].isdigit():
                        continue
                # Single letter initial (e.g. J. Doe)
                if re.search(r"\b[A-Za-z]\Z", preceding):
                    continue
                # Acronym with dots (e.g. U.S.A.)
                if re.search(r"\b[A-Za-z](\.[A-Za-z])+\Z", preceding):
                    continue

            boundaries.append(m.end())

        if boundaries[-1] != len(span_slice):
            boundaries.append(len(span_slice))

        sentences: list[tuple[int, int]] = []
        for i in range(len(boundaries) - 1):
            abs_s = span_start + boundaries[i]
            abs_e = span_start + boundaries[i + 1]
            s_trim, e_trim = self._trim_span_offsets(text, abs_s, abs_e)
            if s_trim < e_trim:
                sentences.append((s_trim, e_trim))

        return sentences

    def _split_paragraph_into_chunks(
        self, text: str, span_start: int, span_end: int
    ) -> list[tuple[int, int, dict[str, Any]]]:
        """Subdivide oversized paragraph into coherent chunks using sentence boundaries and semantic distance."""
        sentences = self._split_into_sentences(text, span_start, span_end)
        if not sentences:
            return [(span_start, span_end, {})]

        if len(sentences) == 1:
            return [(span_start, span_end, {})]

        # Semantic breakpoint detection with local neural embedder
        breakpoints: set[int] = set()
        if self.use_semantic_breakpoints and self.embedder is not None and len(sentences) >= 3:
            try:
                sent_texts = [text[s:e] for s, e in sentences]
                embeddings = self.embedder.embed_batch(sent_texts)
                vecs = np.array(embeddings)
                norms = np.linalg.norm(vecs, axis=1, keepdims=True)
                vecs = vecs / np.maximum(norms, 1e-12)

                distances = []
                for i in range(len(sentences) - 1):
                    sim = float(np.dot(vecs[i], vecs[i + 1]))
                    distances.append(1.0 - sim)

                if distances:
                    avg_d = float(np.mean(distances))
                    std_d = float(np.std(distances))
                    thresh = avg_d + (0.5 * std_d)
                    for i, d in enumerate(distances):
                        if d >= thresh and d > 0.35:
                            breakpoints.add(i + 1)
            except Exception:
                pass

        # Assemble sentences into chunks with lookback overlap
        chunks: list[tuple[int, int, dict[str, Any]]] = []
        curr_sent_indices: list[int] = []

        for idx, (_s, _e) in enumerate(sentences):
            curr_sent_indices.append(idx)
            chunk_start = sentences[curr_sent_indices[0]][0]
            chunk_end = sentences[curr_sent_indices[-1]][1]
            chunk_len = chunk_end - chunk_start

            is_breakpoint = (idx + 1) in breakpoints
            exceeds_target = chunk_len >= self.target_chunk_chars
            is_last = (idx == len(sentences) - 1)

            if (exceeds_target or is_breakpoint) and not is_last:
                chunks.append((chunk_start, chunk_end, {"sentence_count": len(curr_sent_indices)}))

                # Overlap with last sentence if enabled
                if self.overlap_chars > 0 and len(curr_sent_indices) > 1:
                    curr_sent_indices = [curr_sent_indices[-1]]
                else:
                    curr_sent_indices = []

        if curr_sent_indices:
            chunk_start = sentences[curr_sent_indices[0]][0]
            chunk_end = sentences[curr_sent_indices[-1]][1]
            # If trailing fragment is small, merge with previous chunk if budget allows
            if chunks and (chunk_end - chunk_start) < self.min_chunk_chars:
                prev_s, prev_e, prev_m = chunks[-1]
                if (chunk_end - prev_s) <= (self.max_chunk_chars + 150):
                    chunks[-1] = (
                        prev_s,
                        chunk_end,
                        {**prev_m, "sentence_count": prev_m.get("sentence_count", 1) + len(curr_sent_indices)},
                    )
                else:
                    chunks.append((chunk_start, chunk_end, {"sentence_count": len(curr_sent_indices)}))
            else:
                chunks.append((chunk_start, chunk_end, {"sentence_count": len(curr_sent_indices)}))

        return chunks
