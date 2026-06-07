from __future__ import annotations

import re
from dataclasses import dataclass

from nexus_shared.contracts import ChunkCandidate, ParsedDocument
from nexus_document_parser.hashing import sha256_text

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


class TextChunker:
    def __init__(self, max_chars: int = 1200, overlap_chars: int = 150) -> None:
        if max_chars <= 0:
            raise ValueError("max_chars must be positive")
        if overlap_chars < 0 or overlap_chars >= max_chars:
            raise ValueError("overlap_chars must be non-negative and smaller than max_chars")
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def chunk_document(self, document: ParsedDocument) -> list[ChunkCandidate]:
        blocks = markdown_blocks(document.content)
        if not blocks:
            return []

        chunks: list[ChunkDraft] = []
        current = ""
        current_heading_path: list[str] = []
        current_start = 0
        last_heading_path: list[str] = []
        for block in blocks:
            if current and block.heading_path != current_heading_path:
                chunks.append(
                    ChunkDraft(
                        content=current,
                        heading_path=current_heading_path,
                        char_start=current_start,
                        char_end=block.char_start,
                    )
                )
                current = ""
                current_start = block.char_start
                current_heading_path = block.heading_path

            proposed = block.text if not current else f"{current}\n\n{block.text}"
            if len(proposed) <= self.max_chars:
                if not current:
                    current_start = block.char_start
                    current_heading_path = block.heading_path
                current = proposed
                last_heading_path = block.heading_path
                continue

            if current:
                chunks.append(
                    ChunkDraft(
                        content=current,
                        heading_path=current_heading_path,
                        char_start=current_start,
                        char_end=block.char_start,
                    )
                )
            current = block.text
            current_start = block.char_start
            current_heading_path = block.heading_path
            last_heading_path = block.heading_path

            while len(current) > self.max_chars:
                content = current[: self.max_chars].strip()
                chunks.append(
                    ChunkDraft(
                        content=content,
                        heading_path=current_heading_path,
                        char_start=current_start,
                        char_end=current_start + len(content),
                    )
                )
                current = current[self.max_chars - self.overlap_chars :].strip()
                current_start = max(current_start + self.max_chars - self.overlap_chars, current_start)

        if current:
            chunks.append(
                ChunkDraft(
                    content=current,
                    heading_path=current_heading_path or last_heading_path,
                    char_start=current_start,
                    char_end=len(document.content),
                )
            )

        return [
            ChunkCandidate(
                chunk_index=index,
                content=draft.content,
                content_hash=sha256_text(draft.content),
                token_count=count_tokens(draft.content),
                metadata={
                    "source_path": document.source_path,
                    "title": document.title,
                    "tags": document.tags,
                    "wikilinks": document.wikilinks,
                    "heading_path": draft.heading_path,
                    "section_title": draft.heading_path[-1] if draft.heading_path else None,
                    "char_start": draft.char_start,
                    "char_end": draft.char_end,
                },
            )
            for index, draft in enumerate(chunks)
        ]


def count_tokens(content: str) -> int:
    return len(content.split())


@dataclass(frozen=True)
class MarkdownBlock:
    text: str
    heading_path: list[str]
    char_start: int
    char_end: int


@dataclass(frozen=True)
class ChunkDraft:
    content: str
    heading_path: list[str]
    char_start: int
    char_end: int


def markdown_blocks(content: str) -> list[MarkdownBlock]:
    blocks: list[MarkdownBlock] = []
    heading_stack: list[tuple[int, str]] = []
    position = 0
    current_lines: list[str] = []
    current_start = 0
    current_heading_path: list[str] = []

    def flush(end_position: int) -> None:
        nonlocal current_lines, current_start, current_heading_path
        text = "\n".join(current_lines).strip()
        if text and not is_heading_only(text):
            blocks.append(
                MarkdownBlock(
                    text=text,
                    heading_path=current_heading_path,
                    char_start=current_start,
                    char_end=end_position,
                )
            )
        current_lines = []

    for line in content.splitlines():
        line_start = position
        line_end = line_start + len(line) + 1
        heading = HEADING_PATTERN.match(line.strip())
        if heading:
            flush(line_start)
            level = len(heading.group(1))
            title = heading.group(2).strip()
            heading_stack = [(lvl, value) for lvl, value in heading_stack if lvl < level]
            heading_stack.append((level, title))
            current_heading_path = [value for _, value in heading_stack]
            current_start = line_start
            current_lines = [line]
        elif line.strip() == "":
            flush(line_start)
            current_start = line_end
            current_heading_path = [value for _, value in heading_stack]
        else:
            if not current_lines:
                current_start = line_start
                current_heading_path = [value for _, value in heading_stack]
            current_lines.append(line)
        position = line_end

    flush(len(content))
    return blocks


def is_heading_only(text: str) -> bool:
    return bool(HEADING_PATTERN.match(text.strip()))
