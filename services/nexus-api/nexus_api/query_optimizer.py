"""Graph query optimizer — batching and caching helpers for 50k+ node graphs."""
from __future__ import annotations
from functools import lru_cache
from typing import Any, Callable, TypeVar
import time

T = TypeVar("T")

class BatchLoader:
    """Collects individual lookups and executes them in a single batch call."""

    def __init__(self, batch_fn: Callable[[list[str]], dict[str, Any]], max_batch: int = 100):
        self._batch_fn = batch_fn
        self._max_batch = max_batch

    def load_many(self, keys: list[str]) -> dict[str, Any]:
        """Execute batch lookup, splitting into chunks of max_batch."""
        results: dict[str, Any] = {}
        for i in range(0, len(keys), self._max_batch):
            chunk = keys[i : i + self._max_batch]
            results.update(self._batch_fn(chunk))
        return results


class QueryCache:
    """Simple TTL-based in-process cache for graph query results."""

    def __init__(self, ttl_seconds: float = 60.0):
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Any | None:
        if key in self._store:
            value, ts = self._store[key]
            if time.monotonic() - ts < self._ttl:
                return value
            del self._store[key]
        return None

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (value, time.monotonic())

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)


def cached_graph_lookup(cache: QueryCache, batch_loader: BatchLoader, chunk_ids: list[str]) -> dict[str, Any]:
    """Cache-first batch lookup for graph_for_chunk results."""
    hits: dict[str, Any] = {}
    misses: list[str] = []

    for cid in chunk_ids:
        v = cache.get(cid)
        if v is not None:
            hits[cid] = v
        else:
            misses.append(cid)

    if misses:
        fetched = batch_loader.load_many(misses)
        for k, v in fetched.items():
            cache.set(k, v)
            hits[k] = v

    return hits
