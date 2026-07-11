# Installation

## One-command macOS and Linux install

Run:

```bash
curl --proto '=https' --tlsv1.2 -LsSf https://raw.githubusercontent.com/desenyon/converge/codex/converge-rust-rebuild/install.sh | bash
```

The installer:

1. Detects missing system build tools.
2. Installs them with `apt`, `dnf`, `yum`, `pacman`, `zypper`, or `apk` on Linux.
3. Checks for Xcode Command Line Tools on macOS and opens Apple's installer when required.
4. Installs rustup and the pinned Rust 1.96 toolchain when missing.
5. Installs the pinned uv 0.11.28 release when missing or different.
6. Builds the locked Converge source and installs it to `~/.local/bin/converge`.
7. Adds that directory to the active shell's startup file without duplicating entries.
8. Runs `converge --version` and `uv --version` before reporting success.

Administrator authentication may be requested when the operating system needs to install packages. Apple's Command Line Tools dialog must finish before the script can be rerun. A child installer cannot alter its parent shell, so use the activation command printed at the end or open a new terminal window.

Optional overrides:

```bash
CONVERGE_INSTALL_DIR="$HOME/bin" \
CONVERGE_REF="codex/converge-rust-rebuild" \
  bash install.sh
```

For a local checkout, skip the download with `CONVERGE_SOURCE_DIR="$PWD" bash install.sh`.

## Windows

The current PowerShell release installer is:

```powershell
irm https://raw.githubusercontent.com/desenyon/converge/codex/converge-rust-rebuild/install.ps1 | iex
```

The fully bootstrapping workflow added in this change is Bash-only and targets macOS and Linux.
