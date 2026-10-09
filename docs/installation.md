# Installation

The reliable development path is a reviewed source checkout with Rust 1.96+, native build tools, uv on PATH, and an already installed compatible Python interpreter:

```bash
git clone https://github.com/desenyon/converge.git
cd converge
cargo build --release --locked -p converge-cli -j 2
./target/release/converge doctor
```

Windows uses `target\release\converge.exe` and requires the C/C++ tools for the selected Rust target. CI builds/tests Windows separately; the Bash bootstrap applies to macOS/Linux only.

Review `install.sh` before running it. It may install system packages, install rustup/Rust 1.96.0 and uv 0.11.28, build Converge, copy it to `~/.local/bin`, and append PATH initialization to shell startup files. System package installation may require administrator authentication. On macOS, Apple's Command Line Tools installation must complete before retrying the script.

```bash
# Use the current reviewed checkout, including an unmerged branch:
CONVERGE_SOURCE_DIR="$PWD" bash install.sh

# Or select a remote branch/tag explicitly:
CONVERGE_REF=main CONVERGE_INSTALL_DIR="$HOME/bin" bash install.sh
```

The default remote source is desenyon/converge at main. New shell startup settings do not modify the parent shell; open a new terminal or use the activation instructions printed by the installer. Shell installer acceptance tests use mock tools and do not install system packages.

`install.ps1` is a release-asset downloader, not a source bootstrap. It requires a separately published versioned asset from desenyon/converge; do not infer asset availability from the script's presence. Release publishing is outside this upgrade.

Converge disables Python downloads when executing uv. Install a compatible interpreter before solving a project. A writable `UV_CACHE_DIR` is useful when the default uv cache is inaccessible.
