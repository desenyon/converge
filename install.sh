#!/usr/bin/env bash
set -Eeuo pipefail

rust_version="${CONVERGE_RUST_VERSION:-1.96.0}"
uv_version="${CONVERGE_UV_VERSION:-0.11.28}"
repository="${CONVERGE_REPOSITORY:-https://github.com/desenyon/converge.git}"
ref="${CONVERGE_REF:-main}"
install_dir="${CONVERGE_INSTALL_DIR:-$HOME/.local/bin}"
temporary="$(mktemp -d)"
trap 'rm -rf "$temporary"' EXIT INT TERM

if [[ "$install_dir" == *$'\n'* || "$install_dir" == *'"'* || "$install_dir" == *'`'* || "$install_dir" == *'$'* || "$install_dir" == *'\\'* ]]; then
  printf 'error: CONVERGE_INSTALL_DIR contains unsupported shell metacharacters\n' >&2
  exit 2
fi
[[ "$ref" != -* ]] || { printf 'error: CONVERGE_REF cannot begin with a dash\n' >&2; exit 2; }
[[ "$repository" != -* ]] || { printf 'error: CONVERGE_REPOSITORY cannot begin with a dash\n' >&2; exit 2; }

log() {
  printf '==> %s\n' "$*"
}

fail() {
  printf 'error: %s\n' "$*" >&2
  exit 8
}

have() {
  command -v "$1" >/dev/null 2>&1
}

as_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  elif have sudo; then
    sudo "$@"
  else
    fail "administrator access is required to install system build tools"
  fi
}

install_linux_tools() {
  log "Installing required system build tools"
  if have apt-get; then
    as_root apt-get update
    as_root apt-get install -y build-essential ca-certificates curl git pkg-config
  elif have dnf; then
    as_root dnf install -y @development-tools ca-certificates curl git pkgconf-pkg-config
  elif have yum; then
    as_root yum groupinstall -y "Development Tools"
    as_root yum install -y ca-certificates curl git pkgconfig
  elif have pacman; then
    as_root pacman -Sy --needed --noconfirm base-devel ca-certificates curl git pkgconf
  elif have zypper; then
    as_root zypper --non-interactive install -t pattern devel_basis
    as_root zypper --non-interactive install ca-certificates curl git pkg-config
  elif have apk; then
    as_root apk add --no-cache build-base ca-certificates curl git pkgconf
  else
    fail "missing build tools and no supported package manager was found (apt, dnf, yum, pacman, zypper, or apk)"
  fi
}

ensure_system_tools() {
  local missing=()
  local tool
  for tool in curl git cc make install; do
    have "$tool" || missing+=("$tool")
  done
  [[ "${#missing[@]}" -eq 0 ]] && return

  case "$(uname -s)" in
    Linux) install_linux_tools ;;
    Darwin)
      if have xcode-select && ! xcode-select -p >/dev/null 2>&1; then
        xcode-select --install >/dev/null 2>&1 || true
        fail "macOS Command Line Tools installation was opened; finish it, then rerun this installer"
      fi
      fail "missing required macOS tools: ${missing[*]}; install Xcode Command Line Tools and rerun"
      ;;
    *) fail "unsupported operating system: $(uname -s)" ;;
  esac

  for tool in curl git cc make install; do
    have "$tool" || fail "required tool is still unavailable after installation: $tool"
  done
}

ensure_rust() {
  if ! have rustup; then
    log "Installing rustup"
    curl --fail --location --proto '=https' --tlsv1.2 \
      --output "$temporary/rustup-init.sh" https://sh.rustup.rs
    sh "$temporary/rustup-init.sh" --default-toolchain none --profile minimal -y
    [[ -f "$HOME/.cargo/env" ]] && source "$HOME/.cargo/env"
  fi

  have rustup || fail "rustup installation did not produce a usable command"
  log "Ensuring Rust $rust_version is installed"
  rustup toolchain install "$rust_version" --profile minimal
  rustup run "$rust_version" cargo --version >/dev/null
}

ensure_uv() {
  if have uv && [[ "$(uv --version 2>/dev/null | awk '{print $2}')" == "$uv_version" ]]; then
    return
  fi

  log "Installing uv $uv_version"
  curl --fail --location --proto '=https' --tlsv1.2 \
    --output "$temporary/uv-install.sh" "https://astral.sh/uv/$uv_version/install.sh"
  UV_INSTALL_DIR="$install_dir" UV_NO_MODIFY_PATH=1 sh "$temporary/uv-install.sh"
  [[ -x "$install_dir/uv" ]] || fail "uv installation did not produce $install_dir/uv"
}

checkout_source() {
  if [[ -n "${CONVERGE_SOURCE_DIR:-}" ]]; then
    [[ -f "$CONVERGE_SOURCE_DIR/Cargo.toml" ]] || fail "CONVERGE_SOURCE_DIR is not a Converge source tree"
    printf '%s\n' "$CONVERGE_SOURCE_DIR"
    return
  fi

  local source_dir="$temporary/converge"
  log "Downloading Converge ref $ref" >&2
  git clone --quiet --depth 1 --single-branch --branch "$ref" "$repository" "$source_dir"
  printf '%s\n' "$source_dir"
}

install_converge() {
  local source_dir="$1"
  log "Building Converge with Rust $rust_version"
  (
    cd "$source_dir"
    rustup run "$rust_version" cargo build --release --locked --package converge-cli
  )
  mkdir -p "$install_dir"
  install -m 0755 "$source_dir/target/release/converge" "$install_dir/converge"
}

persist_path() {
  local shell_name rc_file path_line activation
  shell_name="$(basename "${SHELL:-sh}")"
  case "$shell_name" in
    zsh)
      rc_file="$HOME/.zshrc"
      path_line="export PATH=\"$install_dir:\$PATH\""
      activation="source \"$rc_file\""
      ;;
    bash)
      rc_file="$HOME/.bashrc"
      path_line="export PATH=\"$install_dir:\$PATH\""
      activation="source \"$rc_file\""
      ;;
    fish)
      rc_file="$HOME/.config/fish/config.fish"
      path_line="fish_add_path \"$install_dir\""
      activation="source \"$rc_file\""
      ;;
    *)
      rc_file="$HOME/.profile"
      path_line="export PATH=\"$install_dir:\$PATH\""
      activation=". \"$rc_file\""
      ;;
  esac

  mkdir -p "$(dirname "$rc_file")"
  if ! grep -Fq '# Added by the Converge installer' "$rc_file" 2>/dev/null; then
    {
      printf '\n# Added by the Converge installer\n'
      printf '%s\n' "$path_line"
    } >>"$rc_file"
  fi
  printf '%s\n' "$activation"
}

ensure_system_tools
ensure_rust
mkdir -p "$install_dir"
ensure_uv
source_dir="$(checkout_source)"
install_converge "$source_dir"
activation="$(persist_path)"
export PATH="$install_dir:$PATH"

log "Verifying installation"
"$install_dir/converge" --version
if [[ -x "$install_dir/uv" ]]; then
  "$install_dir/uv" --version
else
  uv --version
fi

printf '\nConverge is installed at %s/converge.\n' "$install_dir"
printf 'Open a new terminal, or activate Converge now with:\n\n  %s\n\n' "$activation"
printf 'Then run:\n\n  converge solve .\n'
