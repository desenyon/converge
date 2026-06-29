"""Default .converge.toml scaffold for new repositories."""

from __future__ import annotations

INIT_TEMPLATE = """\
# Converge repository configuration
# Docs: https://github.com/desenyon/converge

# Directories scanned for Python imports (relative to repo root)
# source_roots = ["."]

# Directories treated as test code (unused-in-tests deps are ignored)
# test_roots = ["tests", "test", "testing"]

# Skip re-scanning when source fingerprints are unchanged
incremental_scan = true

# Manifest files `converge fix --apply` may update
# repair_targets = ["pyproject"]

# Optional requirements file for repair (when listed in repair_targets)
# requirements_file = "requirements.txt"
"""
