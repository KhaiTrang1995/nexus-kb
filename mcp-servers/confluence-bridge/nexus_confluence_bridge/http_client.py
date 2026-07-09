from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request


class HttpConfluencePage:
    def __init__(self, id: str, space_key: str, title: str, content: str) -> None:
        self.id = id
        self.space_key = space_key
        self.title = title
        self.content = content


class ConfluenceHttpError(RuntimeError):
    def __init__(self, status_code: int | None, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


class HttpConfluenceClient:
    """Calls the real Confluence REST API (Cloud or Data Center) via stdlib urllib.

    Auth is a bearer token (Confluence Cloud API token or Data Center PAT) --
    matches the same stdlib-only, no-new-dependency pattern used by the LLM
    gateway's OllamaProvider/OpenAIProvider.
    """

    def __init__(self, base_url: str, api_token: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_token = api_token
        self._timeout = timeout

    def list_pages(self, space_key: str, limit: int) -> list[HttpConfluencePage]:
        url = (
            f"{self._base_url}/rest/api/content"
            f"?spaceKey={urllib.parse.quote(space_key)}&limit={limit}&expand=body.storage,space"
        )
        data = self._get_json(url)
        return [self._to_page(item, space_key) for item in data.get("results", [])]

    def get_page(self, page_id: str) -> HttpConfluencePage | None:
        url = f"{self._base_url}/rest/api/content/{urllib.parse.quote(page_id)}?expand=body.storage,space"
        try:
            data = self._get_json(url)
        except ConfluenceHttpError as exc:
            if exc.status_code == 404:
                return None
            raise
        return self._to_page(data, data.get("space", {}).get("key", ""))

    def _get_json(self, url: str) -> dict:
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self._api_token}",
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            raise ConfluenceHttpError(exc.code, f"Confluence API returned HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise ConfluenceHttpError(None, f"Confluence API unreachable: {exc.reason}") from exc

    @staticmethod
    def _to_page(item: dict, fallback_space_key: str) -> HttpConfluencePage:
        space_key = (item.get("space") or {}).get("key") or fallback_space_key
        storage = ((item.get("body") or {}).get("storage") or {}).get("value", "")
        return HttpConfluencePage(
            id=str(item["id"]),
            space_key=space_key,
            title=item.get("title", ""),
            content=storage,
        )
