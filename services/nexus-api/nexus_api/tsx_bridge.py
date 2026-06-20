"""
TechSphereX Bridge — nexus-kb integration with TechSphereX Experience Engine.

Calls TechSphereX API (default: http://localhost:8082) to:
  - intercept()       → get suggestions before write operations
  - save_experience() → record learnings after successful operations
  - deliberate()      → trigger multi-CLI deliberation for architectural decisions

All calls are fire-and-forget safe: failures are logged but never raise so they
never block nexus-kb's own operations.

Config via env:
  TSX_ENGINE_URL  (default: http://localhost:8082)
  TSX_TIMEOUT     (default: 5.0 seconds)
  TSX_ENABLED     (default: 1, set to 0 to disable bridge entirely)
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_URL = os.getenv("TSX_ENGINE_URL", "http://localhost:8082")
_TIMEOUT = float(os.getenv("TSX_TIMEOUT", "5.0"))
_ENABLED = os.getenv("TSX_ENABLED", "1") != "0"


def _client() -> httpx.Client:
    return httpx.Client(timeout=_TIMEOUT)


def intercept(action: str, context: str = "", action_type: str = "write") -> list[dict]:
    """
    Call /api/intercept before write operations to get relevant suggestions.
    Returns list of suggestion dicts, or [] if engine unavailable.
    """
    if not _ENABLED:
        return []
    try:
        with _client() as c:
            r = c.post(f"{_URL}/api/intercept", json={
                "action": action,
                "context": context,
                "action_type": action_type,
            })
            r.raise_for_status()
            data = r.json()
            suggestions = data.get("suggestions", [])
            if suggestions:
                logger.info("TSX intercept: %d suggestion(s) for '%s'", len(suggestions), action[:60])
            return suggestions
    except httpx.ConnectError:
        logger.debug("TSX engine not reachable at %s (non-critical)", _URL)
    except Exception as e:
        logger.warning("TSX intercept failed (non-critical): %s", e)
    return []


def save_experience(
    title: str,
    description: str,
    tags: Optional[list[str]] = None,
    category: str = "nexus-kb",
) -> Optional[str]:
    """
    Save a learning/outcome as a TechSphereX experience.
    Returns the experience ID, or None if failed.
    """
    if not _ENABLED:
        return None
    try:
        with _client() as c:
            r = c.post(f"{_URL}/api/experiences", json={
                "title": title,
                "description": description,
                "category": category,
                "tags": tags or [],
            })
            r.raise_for_status()
            exp_id = r.json().get("id")
            logger.info("TSX experience saved: %s (%s)", title[:60], exp_id)
            return exp_id
    except httpx.ConnectError:
        logger.debug("TSX engine not reachable at %s (non-critical)", _URL)
    except Exception as e:
        logger.warning("TSX save_experience failed (non-critical): %s", e)
    return None


def deliberate(
    topic: str,
    context: str = "",
    from_cli: str = "nexus-kb",
    preferred_consultants: Optional[list[str]] = None,
) -> Optional[str]:
    """
    Trigger a multi-CLI deliberation for architectural/design decisions.
    Returns the deliberation_id so the caller can link back or poll for results.
    """
    if not _ENABLED:
        return None
    try:
        payload: dict = {"topic": topic, "context": context, "from_cli": from_cli}
        if preferred_consultants:
            payload["preferred_consultants"] = preferred_consultants
        with _client() as c:
            r = c.post(f"{_URL}/api/deliberate", json=payload)
            r.raise_for_status()
            d_id = r.json().get("deliberation_id")
            logger.info("TSX deliberation started: %s (id=%s)", topic[:60], d_id)
            return d_id
    except httpx.ConnectError:
        logger.debug("TSX engine not reachable at %s (non-critical)", _URL)
    except Exception as e:
        logger.warning("TSX deliberate failed (non-critical): %s", e)
    return None


def report_status(cli_name: str, status: str, task: Optional[str] = None) -> None:
    """Update CLI status in TechSphereX Fleet Monitor."""
    if not _ENABLED:
        return
    try:
        with _client() as c:
            c.patch(f"{_URL}/api/agents/{cli_name}/status", json={
                "status": status,
                **({"task": task} if task else {}),
            })
    except Exception:
        pass


def submit_goal(
    goal: str,
    submitted_by: str = "nexus-kb",
) -> Optional[str]:
    """
    Submit a goal to TechSphereX Agentic Brain.
    Returns goal_id or None if failed.
    """
    if not _ENABLED:
        return None
    try:
        with _client() as c:
            r = c.post(f"{_URL}/api/goals", json={
                "goal": goal,
                "submitted_by": submitted_by,
            })
            r.raise_for_status()
            data = r.json()
            goal_id = data.get("goal_id") or data.get("id") or data.get("task_id")
            logger.info("TSX goal submitted: %s (id=%s)", goal[:60], goal_id)
            return goal_id
    except httpx.ConnectError:
        logger.debug("TSX engine not reachable at %s (non-critical)", _URL)
    except Exception as e:
        logger.warning("TSX submit_goal failed (non-critical): %s", e)
    return None
