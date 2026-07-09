from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _markitdown_instance():
    # Deferred import: MarkItDown() construction loads an ONNX model (~seconds).
    # Cached so the cost is paid once per process, only when a rich file is converted.
    from markitdown import MarkItDown

    return MarkItDown()


class MarkItDownConverter:
    """DocumentConverter adapter backed by Microsoft markitdown."""

    def convert(self, path: Path) -> str:
        result = _markitdown_instance().convert(str(path))
        return result.text_content
