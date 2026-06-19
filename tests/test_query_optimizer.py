"""Tests for graph query optimizer — BatchLoader, QueryCache, cached_graph_lookup."""
from __future__ import annotations

import time
import unittest
from unittest.mock import MagicMock

from tests import _paths  # noqa: F401

from nexus_api.query_optimizer import BatchLoader, QueryCache, cached_graph_lookup


class TestBatchLoaderSingleChunk(unittest.TestCase):
    """BatchLoader.load_many — all keys fit within max_batch (single call)."""

    def test_single_batch_call_when_keys_below_max(self) -> None:
        batch_fn = MagicMock(return_value={"a": 1, "b": 2, "c": 3})
        loader = BatchLoader(batch_fn=batch_fn, max_batch=100)

        result = loader.load_many(["a", "b", "c"])

        batch_fn.assert_called_once_with(["a", "b", "c"])
        self.assertEqual(result, {"a": 1, "b": 2, "c": 3})

    def test_empty_keys_makes_no_calls(self) -> None:
        batch_fn = MagicMock(return_value={})
        loader = BatchLoader(batch_fn=batch_fn, max_batch=100)

        result = loader.load_many([])

        batch_fn.assert_not_called()
        self.assertEqual(result, {})


class TestBatchLoaderChunking(unittest.TestCase):
    """BatchLoader.load_many — keys exceed max_batch (multiple calls)."""

    def test_splits_into_chunks_when_keys_exceed_max_batch(self) -> None:
        # 5 keys, max_batch=2 → 3 calls: [k0,k1], [k2,k3], [k4]
        all_keys = [f"k{i}" for i in range(5)]

        def fake_batch(keys: list[str]) -> dict[str, int]:
            return {k: int(k[1:]) for k in keys}

        batch_fn = MagicMock(side_effect=fake_batch)
        loader = BatchLoader(batch_fn=batch_fn, max_batch=2)

        result = loader.load_many(all_keys)

        self.assertEqual(batch_fn.call_count, 3)
        self.assertEqual(result, {f"k{i}": i for i in range(5)})

    def test_exact_multiple_of_max_batch(self) -> None:
        # 4 keys, max_batch=2 → exactly 2 calls
        all_keys = ["a", "b", "c", "d"]

        def fake_batch(keys: list[str]) -> dict[str, str]:
            return {k: k.upper() for k in keys}

        batch_fn = MagicMock(side_effect=fake_batch)
        loader = BatchLoader(batch_fn=batch_fn, max_batch=2)

        result = loader.load_many(all_keys)

        self.assertEqual(batch_fn.call_count, 2)
        self.assertEqual(result, {"a": "A", "b": "B", "c": "C", "d": "D"})


class TestQueryCacheMissing(unittest.TestCase):
    """QueryCache.get returns None for keys that have never been set."""

    def test_get_returns_none_for_missing_key(self) -> None:
        cache = QueryCache(ttl_seconds=60.0)
        self.assertIsNone(cache.get("nonexistent"))

    def test_len_zero_on_empty_cache(self) -> None:
        cache = QueryCache(ttl_seconds=60.0)
        self.assertEqual(len(cache), 0)


class TestQueryCacheTTLExpiry(unittest.TestCase):
    """QueryCache.get returns None after TTL has elapsed."""

    def test_expired_entry_returns_none(self) -> None:
        cache = QueryCache(ttl_seconds=0.01)
        cache.set("x", "value")
        time.sleep(0.02)
        self.assertIsNone(cache.get("x"))

    def test_expired_entry_is_evicted_from_store(self) -> None:
        cache = QueryCache(ttl_seconds=0.01)
        cache.set("x", "value")
        time.sleep(0.02)
        cache.get("x")  # triggers eviction
        self.assertEqual(len(cache), 0)


class TestQueryCacheHitWithinTTL(unittest.TestCase):
    """QueryCache.set + get returns the value before TTL expires."""

    def test_get_returns_value_within_ttl(self) -> None:
        cache = QueryCache(ttl_seconds=60.0)
        cache.set("key", {"nodes": [1, 2, 3]})
        result = cache.get("key")
        self.assertEqual(result, {"nodes": [1, 2, 3]})

    def test_len_reflects_stored_entries(self) -> None:
        cache = QueryCache(ttl_seconds=60.0)
        cache.set("a", 1)
        cache.set("b", 2)
        self.assertEqual(len(cache), 2)

    def test_clear_empties_cache(self) -> None:
        cache = QueryCache(ttl_seconds=60.0)
        cache.set("a", 1)
        cache.clear()
        self.assertEqual(len(cache), 0)
        self.assertIsNone(cache.get("a"))


class TestCachedGraphLookupCacheHit(unittest.TestCase):
    """cached_graph_lookup — all keys already in cache, batch_fn never called."""

    def test_no_batch_call_on_full_cache_hit(self) -> None:
        cache = QueryCache(ttl_seconds=60.0)
        cache.set("c1", {"entities": ["A"]})
        cache.set("c2", {"entities": ["B"]})

        batch_fn = MagicMock(return_value={})
        loader = BatchLoader(batch_fn=batch_fn, max_batch=100)

        result = cached_graph_lookup(cache, loader, ["c1", "c2"])

        batch_fn.assert_not_called()
        self.assertEqual(result["c1"], {"entities": ["A"]})
        self.assertEqual(result["c2"], {"entities": ["B"]})


class TestCachedGraphLookupCacheMiss(unittest.TestCase):
    """cached_graph_lookup — nothing in cache, batch_fn called, result cached."""

    def test_batch_fn_called_and_result_stored_in_cache(self) -> None:
        cache = QueryCache(ttl_seconds=60.0)
        batch_fn = MagicMock(return_value={"c1": {"entities": ["X"]}, "c2": {"entities": ["Y"]}})
        loader = BatchLoader(batch_fn=batch_fn, max_batch=100)

        result = cached_graph_lookup(cache, loader, ["c1", "c2"])

        batch_fn.assert_called_once_with(["c1", "c2"])
        self.assertEqual(result, {"c1": {"entities": ["X"]}, "c2": {"entities": ["Y"]}})

        # Verify the results were stored in the cache for future lookups
        self.assertEqual(cache.get("c1"), {"entities": ["X"]})
        self.assertEqual(cache.get("c2"), {"entities": ["Y"]})


class TestCachedGraphLookupPartialHit(unittest.TestCase):
    """cached_graph_lookup — some keys cached, only misses forwarded to batch_fn."""

    def test_only_missing_keys_go_to_batch_fn(self) -> None:
        cache = QueryCache(ttl_seconds=60.0)
        cache.set("c1", {"entities": ["cached"]})

        batch_fn = MagicMock(return_value={"c2": {"entities": ["fetched"]}})
        loader = BatchLoader(batch_fn=batch_fn, max_batch=100)

        result = cached_graph_lookup(cache, loader, ["c1", "c2"])

        # batch_fn should only be called for the miss (c2)
        batch_fn.assert_called_once_with(["c2"])
        self.assertEqual(result["c1"], {"entities": ["cached"]})
        self.assertEqual(result["c2"], {"entities": ["fetched"]})

    def test_partial_hit_populates_cache_for_misses(self) -> None:
        cache = QueryCache(ttl_seconds=60.0)
        cache.set("c1", "hit")

        batch_fn = MagicMock(return_value={"c2": "miss-resolved"})
        loader = BatchLoader(batch_fn=batch_fn, max_batch=100)

        cached_graph_lookup(cache, loader, ["c1", "c2"])

        # c2 should now be in the cache
        self.assertEqual(cache.get("c2"), "miss-resolved")
        # c1 was already there, still there
        self.assertEqual(cache.get("c1"), "hit")


if __name__ == "__main__":
    unittest.main()
