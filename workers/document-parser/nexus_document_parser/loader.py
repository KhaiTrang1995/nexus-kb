from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from nexus_shared.contracts import ParsedDocument, SourceType
from nexus_document_parser.hashing import sha256_text

FRONTMATTER_PATTERN = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
WIKILINK_PATTERN = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
TAG_PATTERN = re.compile(r"(?<!\w)#([A-Za-z0-9_\-/]+)")
SUPPORTED_EXTENSIONS = {".md", ".txt"}
MIME_TYPES = {
    ".md": "text/markdown",
    ".txt": "text/plain",
}


def load_markdown_file(path: Path, source_type: SourceType) -> ParsedDocument:
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".md":
        frontmatter, body = parse_frontmatter(raw)
        wikilinks = sorted(extract_wikilinks(body))
    else:
        frontmatter, body = {}, raw
        wikilinks = []
    title = infer_title(path, body, frontmatter)
    tags = sorted(extract_tags(body, frontmatter))
    return ParsedDocument(
        source_type=source_type,
        source_path=str(path.resolve()),
        file_extension=path.suffix.lower(),
        mime_type=MIME_TYPES[path.suffix.lower()],
        title=title,
        content=body.strip(),
        content_hash=sha256_text(body.strip()),
        frontmatter=frontmatter,
        tags=tags,
        wikilinks=wikilinks,
    )


def load_documents(source_path: str, source_type: SourceType) -> list[ParsedDocument]:
    root = Path(source_path)
    if not root.exists():
        raise FileNotFoundError(f"source path does not exist: {source_path}")
    if root.is_file():
        if root.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return []
        return [load_markdown_file(root, source_type)]

    documents: list[ParsedDocument] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            documents.append(load_markdown_file(path, source_type))
    return documents


def parse_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    match = FRONTMATTER_PATTERN.match(raw)
    if not match:
        return {}, raw

    parsed = yaml.safe_load(match.group(1)) or {}
    if not isinstance(parsed, dict):
        parsed = {}
    body = raw[match.end() :]
    return parsed, body


def infer_title(path: Path, body: str, frontmatter: dict[str, Any]) -> str:
    title = frontmatter.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()

    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()

    return path.stem


def extract_tags(body: str, frontmatter: dict[str, Any]) -> set[str]:
    tags: set[str] = set(TAG_PATTERN.findall(body))
    frontmatter_tags = frontmatter.get("tags", [])
    if isinstance(frontmatter_tags, str):
        tags.add(frontmatter_tags.strip("# "))
    elif isinstance(frontmatter_tags, list):
        for tag in frontmatter_tags:
            if isinstance(tag, str):
                tags.add(tag.strip("# "))
    return {tag for tag in tags if tag}


def extract_wikilinks(body: str) -> set[str]:
    return {match.strip() for match in WIKILINK_PATTERN.findall(body) if match.strip()}
