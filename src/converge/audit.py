"""Append-only audit log for validated repairs under .converge/."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from converge.project_context import ProjectContext


def append_audit_event(context: ProjectContext, event: dict[str, Any]) -> None:
    """Append one JSON line to the audit log."""
    context.artifact_dir.mkdir(parents=True, exist_ok=True)
    payload = {"ts": datetime.now(tz=UTC).isoformat(), **event}
    line = json.dumps(payload, sort_keys=True) + "\n"
    with context.audit_log_path.open("a", encoding="utf-8") as handle:
        handle.write(line)
