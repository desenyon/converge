# Installation

Release archives target x86-64 Linux, ARM64 Linux, x86-64 macOS, ARM64 macOS, and x86-64 Windows.

Unix:

```bash
curl --proto '=https' --tlsv1.2 -LsSf https://raw.githubusercontent.com/concatenate-ai/converge/main/install.sh | sh
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/concatenate-ai/converge/main/install.ps1 | iex
```

Both installers verify the release SHA-256 checksum before installing. From source, run `cargo install --path crates/converge-cli`.
