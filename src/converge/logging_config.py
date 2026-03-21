"""stderr logging for CLI; keeps stdout clean for --json."""

from __future__ import annotations

import logging
import sys


def configure_cli_logging(verbose: bool) -> None:
    """Install a single handler on the converge.* loggers (DEBUG if verbose, else WARNING)."""
    level = logging.DEBUG if verbose else logging.WARNING
    log = logging.getLogger("converge")
    log.setLevel(level)
    if log.handlers:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    log.addHandler(handler)
    log.propagate = False
