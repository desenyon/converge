"""Incremental scan fingerprinting (full-tree hash short-circuit)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def load_scan_state(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}


def fingerprint_files(root: Path, py_files: list[Path]) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in py_files:
        try:
            rel = p.relative_to(root).as_posix()
        except ValueError:
            continue
        try:
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
        except OSError:
            continue
        out[rel] = digest
    return out


def is_tree_unchanged(state_path: Path, root: Path, py_files: list[Path]) -> bool:
    prev = load_scan_state(state_path)
    if not prev:
        return False
    cur = fingerprint_files(root, py_files)
    return prev == cur and len(prev) == len(cur) and len(prev) > 0


def write_scan_state(state_path: Path, root: Path, py_files: list[Path]) -> None:
    fp = fingerprint_files(root, py_files)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(dict(sorted(fp.items())), indent=2) + "\n", encoding="utf-8")


def classify_file_changes(
    prev: dict[str, str], cur_fp: dict[str, str]
) -> tuple[set[str], set[str], set[str]]:
    """
    Compare prior fingerprints to current.

    Returns (paths_to_reparse, paths_removed, paths_unchanged).
    """
    removed = set(prev.keys()) - set(cur_fp.keys())
    unchanged = {rel for rel in cur_fp if prev.get(rel) == cur_fp[rel]}
    to_reparse = set(cur_fp.keys()) - unchanged
    return to_reparse, removed, unchanged
