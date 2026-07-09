from __future__ import annotations

import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from tests import _paths  # noqa: F401

from nexus_confluence_bridge.http_client import ConfluenceHttpError, HttpConfluenceClient


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class HttpConfluenceClientTest(unittest.TestCase):
    def test_list_pages_parses_results_and_sends_bearer_token(self) -> None:
        client = HttpConfluenceClient(base_url="https://example.atlassian.net/wiki", api_token="secret-token")
        payload = {
            "results": [
                {
                    "id": "123",
                    "title": "Runbook",
                    "space": {"key": "KB"},
                    "body": {"storage": {"value": "<p>hello</p>"}},
                }
            ]
        }

        with patch("urllib.request.urlopen", return_value=FakeResponse(payload)) as mock_urlopen:
            pages = client.list_pages("KB", limit=10)

        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].id, "123")
        self.assertEqual(pages[0].title, "Runbook")
        self.assertEqual(pages[0].space_key, "KB")
        self.assertEqual(pages[0].content, "<p>hello</p>")

        sent_request = mock_urlopen.call_args[0][0]
        self.assertEqual(sent_request.get_header("Authorization"), "Bearer secret-token")
        self.assertIn("spaceKey=KB", sent_request.full_url)

    def test_get_page_returns_none_on_404(self) -> None:
        client = HttpConfluenceClient(base_url="https://example.atlassian.net/wiki", api_token="secret-token")
        http_error = urllib.error.HTTPError(url="x", code=404, msg="not found", hdrs=None, fp=io.BytesIO(b""))

        with patch("urllib.request.urlopen", side_effect=http_error):
            page = client.get_page("999")

        self.assertIsNone(page)

    def test_get_page_reraises_non_404_errors(self) -> None:
        client = HttpConfluenceClient(base_url="https://example.atlassian.net/wiki", api_token="secret-token")
        http_error = urllib.error.HTTPError(url="x", code=500, msg="boom", hdrs=None, fp=io.BytesIO(b""))

        with patch("urllib.request.urlopen", side_effect=http_error):
            with self.assertRaises(ConfluenceHttpError) as ctx:
                client.get_page("999")
        self.assertEqual(ctx.exception.status_code, 500)

    def test_network_error_is_wrapped_without_leaking_url_details(self) -> None:
        client = HttpConfluenceClient(base_url="https://example.atlassian.net/wiki", api_token="secret-token")
        url_error = urllib.error.URLError("Name or service not known")

        with patch("urllib.request.urlopen", side_effect=url_error):
            with self.assertRaises(ConfluenceHttpError):
                client.list_pages("KB", limit=10)


if __name__ == "__main__":
    unittest.main()
