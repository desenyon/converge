"""Path filtering and module classification for repository scans."""

from __future__ import annotations

from pathlib import Path

from converge.settings import ConvergeSettings


def should_skip_path(path: Path, root: Path, settings: ConvergeSettings) -> bool:
    """Skip virtualenvs, tooling caches, and hidden directories (except known roots)."""
    try:
        rel = path.relative_to(root)
    except ValueError:
        return True
    for part in rel.parts:
        if part in settings.ignore_dir_names:
            return True
        if part.startswith(".") and part not in {".", ".."}:
            return True
        if part in ("venv", "env", "node_modules"):
            return True
    return False


def module_scan_kind(rel_path: Path, settings: ConvergeSettings) -> str:
    """Classify a module path as test code vs application source for diagnostics."""
    s = rel_path.as_posix()
    for tr in settings.test_roots:
        t = tr.strip("/\\")
        if not t or t == ".":
            continue
        if s == t or s.startswith(t + "/"):
            return "test"
    return "source"


def iter_python_files(root: Path, settings: ConvergeSettings) -> list[Path]:
    """All *.py files under the repository (and extra_scan_roots) subject to ignores."""
    roots: list[Path] = [root]
    for extra in settings.extra_scan_roots:
        roots.append((root / extra).resolve())

    seen: set[Path] = set()
    files: list[Path] = []
    for base in roots:
        if not base.is_dir():
            continue
        for p in base.rglob("*.py"):
            if p in seen:
                continue
            if should_skip_path(p, root, settings):
                continue
            seen.add(p)
            files.append(p)
    return sorted(files)
