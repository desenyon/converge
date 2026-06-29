"""Append-only audit log for validated repairs under .converge/."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from converge.project_context import ProjectContext


def read_audit_events(context: ProjectContext, *, limit: int | None = None) -> list[dict[str, Any]]:
    """Read audit log entries (newest last)."""
    if not context.audit_log_path.is_file():
        return []
    events: list[dict[str, Any]] = []
    with context.audit_log_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                events.append(payload)
    if limit is not None and limit > 0:
        return events[-limit:]
    return events


def append_audit_event(context: ProjectContext, event: dict[str, Any]) -> None:
    """Append one JSON line to the audit log."""
    context.artifact_dir.mkdir(parents=True, exist_ok=True)
    payload = {"ts": datetime.now(tz=UTC).isoformat(), **event}
    line = json.dumps(payload, sort_keys=True) + "\n"
    with context.audit_log_path.open("a", encoding="utf-8") as handle:
        handle.write(line)
