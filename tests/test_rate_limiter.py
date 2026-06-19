from __future__ import annotations

import unittest
from unittest.mock import patch

from tests import _paths  # noqa: F401 — adds packages to sys.path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from nexus_api.middleware.rate_limiter import RateLimiterMiddleware


def _make_app(rpm: int = 60, enabled: bool = True) -> FastAPI:
    """Build a minimal FastAPI app with RateLimiterMiddleware already attached."""
    inner = FastAPI()

    @inner.get("/health")
    def health():
        return {"status": "ok"}

    @inner.get("/ping")
    def ping():
        return {"pong": True}

    inner.add_middleware(RateLimiterMiddleware, rpm=rpm, enabled=enabled)
    return inner


class RateLimiterAllowWithinLimitTest(unittest.TestCase):
    """5 requests within an rpm=60 budget — all should pass."""

    def test_allow_within_limit(self) -> None:
        client = TestClient(_make_app(rpm=60))
        for i in range(5):
            resp = client.get("/ping")
            self.assertEqual(resp.status_code, 200, f"Request {i + 1} was unexpectedly blocked")


class RateLimiterBlockOverLimitTest(unittest.TestCase):
    """rpm=2: first two pass, third must get 429."""

    def test_block_when_over_limit(self) -> None:
        client = TestClient(_make_app(rpm=2))
        resp1 = client.get("/ping")
        resp2 = client.get("/ping")
        resp3 = client.get("/ping")

        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp3.status_code, 429)


class RateLimiterHealthExemptTest(unittest.TestCase):
    """/health must always pass even when rpm=1 is exceeded."""

    def test_health_exempt(self) -> None:
        client = TestClient(_make_app(rpm=1))
        resp1 = client.get("/health")
        resp2 = client.get("/health")

        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp2.status_code, 200)


class RateLimiterRetryAfterHeaderTest(unittest.TestCase):
    """429 response must carry a Retry-After header."""

    def test_retry_after_header_present(self) -> None:
        client = TestClient(_make_app(rpm=1))
        client.get("/ping")          # consume the single slot
        resp = client.get("/ping")   # this one gets throttled

        self.assertEqual(resp.status_code, 429)
        self.assertIn("retry-after", resp.headers)
        retry_val = int(resp.headers["retry-after"])
        self.assertGreater(retry_val, 0)


class RateLimiterWindowResetTest(unittest.TestCase):
    """After the window expires the counter resets and new requests are allowed."""

    def test_window_reset(self) -> None:
        app = _make_app(rpm=1)
        fake_time = 0.0

        def monotonic_side_effect():
            return fake_time

        with patch("nexus_api.middleware.rate_limiter.time.monotonic", side_effect=monotonic_side_effect):
            client = TestClient(app)

            # First request at t=0 fills the single slot
            resp1 = client.get("/ping")
            self.assertEqual(resp1.status_code, 200)

            # Second request at t=0 still inside window → 429
            resp2 = client.get("/ping")
            self.assertEqual(resp2.status_code, 429)

            # Advance time past the 60-second window
            fake_time = 61.0

            # Third request should now be allowed (old entry evicted)
            resp3 = client.get("/ping")
            self.assertEqual(resp3.status_code, 200)


class RateLimiterDisabledTest(unittest.TestCase):
    """When enabled=False every request passes regardless of rpm."""

    def test_disabled_always_passes(self) -> None:
        client = TestClient(_make_app(rpm=1, enabled=False))
        for i in range(5):
            resp = client.get("/ping")
            self.assertEqual(resp.status_code, 200, f"Request {i + 1} should pass when middleware is disabled")


if __name__ == "__main__":
    unittest.main()
