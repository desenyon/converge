"""Robust parsing of conflict IDs emitted by ConflictDetector."""

from __future__ import annotations

import re
from typing import Any


def parse_conflict_id(conflict_id: str) -> dict[str, Any]:
    """
    Parse conflict IDs such as:
    - conflict:unresolved_mod:main.py_pkg:requests
    - conflict:unused_pkg:requests
    - conflict:clash_pkg:foo_pkg:bar
    """
    if not conflict_id.startswith("conflict:"):
        return {"kind": "invalid", "error": "not_a_conflict_id", "raw": conflict_id}

    m = re.match(r"^conflict:unresolved_(mod:.+)_pkg:(.+)$", conflict_id)
    if m:
        return {
            "kind": "unresolved_import",
            "module": m.group(1),
            "import_target": f"pkg:{m.group(2)}",
            "package_name": m.group(2),
        }

    m = re.match(r"^conflict:unused_(pkg:.+)$", conflict_id)
    if m:
        return {"kind": "unused_dependency", "package_ref": m.group(1)}

    m = re.match(r"^conflict:clash_(.+)$", conflict_id)
    if m:
        return {"kind": "version_clash", "raw": m.group(1)}

    return {"kind": "unknown_shape", "raw": conflict_id}
