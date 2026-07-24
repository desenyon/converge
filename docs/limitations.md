# Limitations

The verified 0.1 path is PEP 621 `pyproject.toml` plus uv, with read-only discovery for Poetry, Conda environment files, requirements files, uv workspaces, and static Python imports.

Not yet release-proven:

- Poetry, Conda, setup.py/setup.cfg, and PEP 723 repair or environment creation;
- dynamic-import and type-checking-only classification;
- local/Git dependency repair beyond discovery evidence;
- container, Node, Rust, and system-package plugins;
- OS namespace or macOS sandbox hardening;
- automatic project test-command execution;
- vulnerability, SBOM, and secret-scanner adapters;
- MCP transport serving and impact analysis.

Poetry/Conda/workspace formats are discoverable and modeled; repair and authoritative environment creation for those backends are not claimed until acceptance fixtures pass validation and apply stages.
