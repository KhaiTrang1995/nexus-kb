"""Simple Redis cache with in-process dict fallback when Redis unavailable."""
from __future__ import annotations
import json, os
from typing import Any, Optional

_store: dict[str, str] = {}  # in-process fallback

try:
    import redis as _redis
    _client = _redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)
    _client.ping()
    _USE_REDIS = True
except Exception:
    _client = None
    _USE_REDIS = False

TTL = int(os.getenv("ENTITY_CACHE_TTL", "300"))  # seconds

def get(key: str) -> Optional[Any]:
    if _USE_REDIS and _client:
        v = _client.get(key)
        return json.loads(v) if v else None
    return json.loads(_store[key]) if key in _store else None

def set(key: str, value: Any, ttl: int = TTL) -> None:
    if _USE_REDIS and _client:
        _client.setex(key, ttl, json.dumps(value))
    else:
        _store[key] = json.dumps(value)

def delete(key: str) -> None:
    if _USE_REDIS and _client:
        _client.delete(key)
    else:
        _store.pop(key, None)

def clear() -> None:
    if _USE_REDIS and _client:
        _client.flushdb()
    else:
        _store.clear()
