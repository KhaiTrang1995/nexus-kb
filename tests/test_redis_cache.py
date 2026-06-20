"""Tests for nexus_api.cache — Redis TTL cache with in-process dict fallback.

All tests exercise the in-process fallback path so they work without a real
Redis server.  The fallback is forced via monkeypatching the module-level
flags _USE_REDIS and _client after import.
"""
from __future__ import annotations

import importlib
import os
import sys
import unittest

from tests import _paths  # noqa: F401 — adds service packages to sys.path


def _load_cache_module(*, use_redis: bool = False):
    """Import (or reimport) nexus_api.cache with Redis disabled.

    We pop the cached module so each test class gets a clean _store.
    """
    for key in list(sys.modules):
        if key in ("nexus_api.cache",):
            del sys.modules[key]

    import nexus_api.cache as mod

    # Force fallback mode regardless of whether a real Redis is present.
    mod._USE_REDIS = use_redis
    mod._client = None
    mod._store.clear()
    return mod


class TestCacheGetMissingKey(unittest.TestCase):
    """get() returns None for a key that has never been set."""

    def setUp(self) -> None:
        self.cache = _load_cache_module()

    def test_get_missing_returns_none(self) -> None:
        result = self.cache.get("nonexistent-key")
        self.assertIsNone(result)


class TestCacheSetAndGet(unittest.TestCase):
    """set() followed by get() round-trips a dict value correctly."""

    def setUp(self) -> None:
        self.cache = _load_cache_module()

    def test_set_and_get_dict(self) -> None:
        payload = {"entity": "Qdrant", "type": "vector_db", "score": 0.97}
        self.cache.set("chunk:abc123", payload)
        result = self.cache.get("chunk:abc123")
        self.assertEqual(result, payload)

    def test_set_and_get_list(self) -> None:
        payload = [{"id": 1}, {"id": 2}]
        self.cache.set("chunk:list-key", payload)
        result = self.cache.get("chunk:list-key")
        self.assertEqual(result, payload)

    def test_set_and_get_string(self) -> None:
        self.cache.set("chunk:str-key", "hello world")
        result = self.cache.get("chunk:str-key")
        self.assertEqual(result, "hello world")

    def test_set_and_get_integer(self) -> None:
        self.cache.set("chunk:int-key", 42)
        result = self.cache.get("chunk:int-key")
        self.assertEqual(result, 42)


class TestCacheDelete(unittest.TestCase):
    """delete() removes an existing key; subsequent get() returns None."""

    def setUp(self) -> None:
        self.cache = _load_cache_module()

    def test_delete_existing_key(self) -> None:
        self.cache.set("chunk:to-delete", {"x": 1})
        self.cache.delete("chunk:to-delete")
        self.assertIsNone(self.cache.get("chunk:to-delete"))

    def test_delete_nonexistent_key_does_not_raise(self) -> None:
        # Should be a silent no-op.
        try:
            self.cache.delete("chunk:never-existed")
        except Exception as exc:  # pragma: no cover
            self.fail(f"delete() raised unexpectedly: {exc}")


class TestCacheClear(unittest.TestCase):
    """clear() removes all keys from the store."""

    def setUp(self) -> None:
        self.cache = _load_cache_module()

    def test_clear_empties_store(self) -> None:
        self.cache.set("k1", {"a": 1})
        self.cache.set("k2", {"b": 2})
        self.cache.set("k3", {"c": 3})
        self.cache.clear()
        self.assertIsNone(self.cache.get("k1"))
        self.assertIsNone(self.cache.get("k2"))
        self.assertIsNone(self.cache.get("k3"))

    def test_clear_on_empty_store_does_not_raise(self) -> None:
        try:
            self.cache.clear()
        except Exception as exc:  # pragma: no cover
            self.fail(f"clear() raised unexpectedly: {exc}")


class TestCacheFallbackWhenRedisUnavailable(unittest.TestCase):
    """In-process dict fallback is used when Redis is unavailable (_USE_REDIS=False)."""

    def setUp(self) -> None:
        # _load_cache_module already sets _USE_REDIS=False and _client=None.
        self.cache = _load_cache_module(use_redis=False)

    def test_fallback_set_and_get(self) -> None:
        self.assertFalse(self.cache._USE_REDIS)
        self.assertIsNone(self.cache._client)
        self.cache.set("entity:fallback", {"name": "Nexus-KB"})
        result = self.cache.get("entity:fallback")
        self.assertEqual(result, {"name": "Nexus-KB"})

    def test_fallback_delete(self) -> None:
        self.cache.set("entity:del", {"name": "tmp"})
        self.cache.delete("entity:del")
        self.assertIsNone(self.cache.get("entity:del"))

    def test_fallback_clear(self) -> None:
        self.cache.set("entity:a", 1)
        self.cache.set("entity:b", 2)
        self.cache.clear()
        self.assertIsNone(self.cache.get("entity:a"))
        self.assertIsNone(self.cache.get("entity:b"))

    def test_fallback_store_is_dict(self) -> None:
        # _store is the in-process backing dict; ensure it is used.
        self.cache.set("entity:inspect", {"ok": True})
        self.assertIn("entity:inspect", self.cache._store)


class TestCacheTTLFromEnv(unittest.TestCase):
    """TTL is read from the ENTITY_CACHE_TTL environment variable at import time."""

    def test_default_ttl_is_300(self) -> None:
        # Remove the env var if present so we get the default.
        os.environ.pop("ENTITY_CACHE_TTL", None)
        cache = _load_cache_module()
        # Re-read TTL from the fresh module (import evaluates the int() call).
        import nexus_api.cache as fresh
        self.assertEqual(fresh.TTL, 300)

    def test_custom_ttl_from_env(self) -> None:
        os.environ["ENTITY_CACHE_TTL"] = "60"
        # Force a clean reimport so the module-level int() re-evaluates.
        for key in list(sys.modules):
            if key == "nexus_api.cache":
                del sys.modules[key]
        import nexus_api.cache as fresh
        self.assertEqual(fresh.TTL, 60)
        # Clean up to avoid polluting other tests.
        os.environ.pop("ENTITY_CACHE_TTL", None)


if __name__ == "__main__":
    unittest.main()
