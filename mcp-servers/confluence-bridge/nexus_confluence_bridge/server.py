from __future__ import annotations

import json
import sys
from typing import Any

from nexus_confluence_bridge.bridge import ConfluenceBridge, InMemoryConfluenceClient, InMemoryConfluencePage


def build_demo_bridge() -> ConfluenceBridge:
    return ConfluenceBridge(
        InMemoryConfluenceClient(
            [
                InMemoryConfluencePage(
                    id="demo-page-1",
                    space_key="KB",
                    title="Synthetic Runbook",
                    content="Synthetic Confluence content for local connector verification.",
                )
            ]
        )
    )


def handle_json_request(raw: str, bridge: ConfluenceBridge | None = None) -> str:
    request = json.loads(raw)
    result = (bridge or build_demo_bridge()).call_tool_result(
        name=request["tool"],
        payload=request.get("arguments") or {},
    )
    return json.dumps(result.model_dump(), sort_keys=True)


def main(argv: list[str] | None = None) -> int:
    _ = argv or sys.argv[1:]
    try:
        raw = sys.stdin.read()
        sys.stdout.write(handle_json_request(raw))
        sys.stdout.write("\n")
        return 0
    except Exception as exc:
        sys.stdout.write(
            json.dumps(
                {
                    "tool": "unknown",
                    "ok": False,
                    "error_code": "INVALID_REQUEST",
                    "error_message": str(exc),
                },
                sort_keys=True,
            )
        )
        sys.stdout.write("\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
