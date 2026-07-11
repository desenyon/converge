#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
temporary="$(mktemp -d)"
trap 'rm -rf "$temporary"' EXIT

home="$temporary/home"
mock_bin="$temporary/mock-bin"
install_dir="$home/.local/bin"
source_dir="$temporary/source"
mkdir -p "$home" "$mock_bin" "$source_dir"
touch "$source_dir/Cargo.toml"

cat >"$mock_bin/cargo" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "--version" ]]; then
  echo "cargo 1.96.0"
  exit 0
fi
if [[ "${1:-}" == "build" ]]; then
  mkdir -p target/release
  cat >target/release/converge <<'BINARY'
#!/usr/bin/env bash
echo "converge 0.1.0"
BINARY
  chmod +x target/release/converge
  exit 0
fi
exit 1
MOCK

cat >"$mock_bin/rustup" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "run" ]]; then
  shift 2
  exec "$@"
fi
exit 0
MOCK

cat >"$mock_bin/uv" <<'MOCK'
#!/usr/bin/env bash
echo "uv 0.11.28"
MOCK

chmod +x "$mock_bin/cargo" "$mock_bin/rustup" "$mock_bin/uv"

run_installer() {
  HOME="$home" \
  SHELL=/bin/bash \
  PATH="$mock_bin:/usr/bin:/bin" \
  CONVERGE_SOURCE_DIR="$source_dir" \
  CONVERGE_INSTALL_DIR="$install_dir" \
    bash "$repository_root/install.sh"
}

first_output="$(run_installer)"
[[ -x "$install_dir/converge" ]]
[[ "$($install_dir/converge --version)" == "converge 0.1.0" ]]
grep -Fq '# Added by the Converge installer' "$home/.bashrc"
grep -Fq "export PATH=\"$install_dir:\$PATH\"" "$home/.bashrc"
grep -Fq 'Open a new terminal, or activate Converge now with:' <<<"$first_output"

run_installer >/dev/null
[[ "$(grep -Fc '# Added by the Converge installer' "$home/.bashrc")" -eq 1 ]]

echo "installer acceptance test passed"
