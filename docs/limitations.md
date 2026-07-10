# Limitations

The verified 0.1 path is PEP 621 `pyproject.toml` plus uv, standard requirements files for discovery, and static Python imports.

Not yet release-proven:

- Poetry, Conda, setup.py/setup.cfg mutation, and PEP 723 repair;
- dynamic-import and type-checking-only classification;
- Python workspaces and local/Git dependency repair;
- container, Node, Rust, and system-package plugins;
- OS namespace or macOS sandbox hardening;
- automatic project test-command execution;
- vulnerability, SBOM, and secret-scanner adapters;
- MCP transport serving and impact analysis.

These formats are not claimed as supported until acceptance fixtures pass.
