"""Stable CLI exit codes for automation (CI, scripts)."""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    """Converge process exit codes."""

    SUCCESS = 0
    """Command completed; no actionable issues (or scan/export succeeded)."""

    ISSUES_FOUND = 1
    """Completed successfully but dependency issues or conflicts were found."""

    ERROR = 2
    """Usage error, missing graph, I/O failure, or other fatal error."""
