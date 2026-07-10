#!/bin/sh
set -eu

version="${CONVERGE_VERSION:-0.1.0}"
install_dir="${CONVERGE_INSTALL_DIR:-$HOME/.local/bin}"
repository="https://github.com/concatenate-ai/converge"

case "$(uname -s)-$(uname -m)" in
  Linux-x86_64) target="x86_64-unknown-linux-gnu" ;;
  Linux-aarch64|Linux-arm64) target="aarch64-unknown-linux-gnu" ;;
  Darwin-x86_64) target="x86_64-apple-darwin" ;;
  Darwin-arm64) target="aarch64-apple-darwin" ;;
  *) echo "unsupported platform: $(uname -s) $(uname -m)" >&2; exit 2 ;;
esac

archive="converge-${target}.tar.xz"
base="${repository}/releases/download/v${version}"
temporary="$(mktemp -d)"
trap 'rm -rf "$temporary"' EXIT INT TERM

curl --fail --location --proto '=https' --tlsv1.2 \
  --output "$temporary/$archive" "$base/$archive"
curl --fail --location --proto '=https' --tlsv1.2 \
  --output "$temporary/$archive.sha256" "$base/$archive.sha256"

if command -v sha256sum >/dev/null 2>&1; then
  (cd "$temporary" && sha256sum --check "$archive.sha256")
else
  expected="$(cut -d ' ' -f 1 "$temporary/$archive.sha256")"
  actual="$(shasum -a 256 "$temporary/$archive" | cut -d ' ' -f 1)"
  test "$expected" = "$actual" || { echo "checksum verification failed" >&2; exit 5; }
fi

tar -xJf "$temporary/$archive" -C "$temporary"
mkdir -p "$install_dir"
install -m 0755 "$temporary/converge" "$install_dir/converge"
echo "installed converge to $install_dir/converge"
