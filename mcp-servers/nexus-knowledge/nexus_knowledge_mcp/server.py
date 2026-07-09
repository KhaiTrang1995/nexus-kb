from __future__ import annotations

import json
import sys

from nexus_knowledge_mcp.bridge import NexusKnowledgeBridge
from nexus_knowledge_mcp.schemas import ToolCallEnvelope


def handle_json_request(raw: str, bridge: NexusKnowledgeBridge | None = None) -> str:
    envelope = ToolCallEnvelope.model_validate(json.loads(raw))
    resolved_bridge = bridge
    if resolved_bridge is None:
        from nexus_knowledge_mcp.wiring import build_bridge

        resolved_bridge = build_bridge()
    result = resolved_bridge.call_tool_result(envelope)
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
