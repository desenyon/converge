# Manual release

Converge is distributed via the install script, not PyPI.

## Maintainer checklist

1. Bump `version` in `pyproject.toml` and align `tool_version` references in docs if needed.
2. Run the full verification suite from `AGENTS.md`.
3. Commit and push to `main`.
4. Tag the release:

```bash
git tag -a "v0.2.0" -m "Converge 0.2.0"
git push origin "v0.2.0"
```

5. Tell users to install or upgrade:

```bash
curl -fsSL https://raw.githubusercontent.com/desenyon/converge/main/install.sh | bash
```

Pin a tag:

```bash
CONVERGE_REF=v0.2.0 curl -fsSL https://raw.githubusercontent.com/desenyon/converge/main/install.sh | bash
```

## Upgrade an existing install

Re-run the install script. It updates the clone under `~/.local/share/converge/app` and reinstalls into the same venv.
