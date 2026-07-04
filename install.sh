#!/usr/bin/env bash
# Install Converge from GitHub into ~/.local/share/converge and link converge into ~/.local/bin.
set -euo pipefail

CONVERGE_HOME="${CONVERGE_HOME:-${HOME}/.local/share/converge}"
BIN_DIR="${CONVERGE_BIN_DIR:-${HOME}/.local/bin}"
REPO_URL="${CONVERGE_REPO_URL:-https://github.com/desenyon/converge.git}"
REF="${CONVERGE_REF:-main}"
APP_DIR="${CONVERGE_HOME}/app"
VENV_DIR="${CONVERGE_HOME}/venv"
WRAPPER="${BIN_DIR}/converge"

info() { printf '\033[36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m!!>\033[0m %s\n' "$*"; }
die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

find_python() {
  local candidate
  for candidate in python3.14 python3.13 python3.12 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
        printf '%s\n' "$candidate"
        return 0
      fi
    fi
  done
  die "Python 3.12+ is required. Install from https://www.python.org/downloads/"
}

ensure_path_line() {
  local profile="$1"
  local line='export PATH="${HOME}/.local/bin:${PATH}"'
  [[ -f "$profile" ]] || return 0
  if grep -Fq '.local/bin' "$profile" 2>/dev/null; then
    return 0
  fi
  {
    printf '\n# Added by Converge install.sh\n'
    printf '%s\n' "$line"
  } >>"$profile"
  info "Updated PATH in ${profile}"
}

setup_path() {
  case ":${PATH}:" in
    *":${BIN_DIR}:"*) ;;
    *)
      ensure_path_line "${HOME}/.zshrc"
      ensure_path_line "${HOME}/.bashrc"
      ensure_path_line "${HOME}/.bash_profile"
      ensure_path_line "${HOME}/.profile"
      export PATH="${BIN_DIR}:${PATH}"
      warn "Open a new shell or run: export PATH=\"${BIN_DIR}:\$PATH\""
      ;;
  esac
}

clone_or_update() {
  mkdir -p "${CONVERGE_HOME}"
  if [[ -d "${APP_DIR}/.git" ]]; then
    info "Updating existing install at ${APP_DIR}"
    git -C "${APP_DIR}" fetch --depth 1 origin "${REF}" 2>/dev/null \
      || git -C "${APP_DIR}" fetch origin
    git -C "${APP_DIR}" checkout "${REF}"
    git -C "${APP_DIR}" pull --ff-only origin "${REF}" 2>/dev/null || true
  else
    info "Cloning ${REPO_URL} (${REF})"
    rm -rf "${APP_DIR}"
    git clone --depth 1 --branch "${REF}" "${REPO_URL}" "${APP_DIR}" \
      || git clone --depth 1 "${REPO_URL}" "${APP_DIR}"
    if [[ "${REF}" != "main" && "${REF}" != "master" ]]; then
      git -C "${APP_DIR}" checkout "${REF}"
    fi
  fi
}

main() {
  need_cmd git
  local python
  python="$(find_python)"
  info "Using ${python}"
  info "Install root: ${CONVERGE_HOME}"

  clone_or_update

  if [[ ! -d "${VENV_DIR}" ]]; then
    info "Creating virtual environment"
    "${python}" -m venv "${VENV_DIR}"
  fi

  info "Installing Converge"
  "${VENV_DIR}/bin/python" -m pip install --upgrade pip wheel >/dev/null
  "${VENV_DIR}/bin/pip" install --upgrade "${APP_DIR}"

  mkdir -p "${BIN_DIR}"
  ln -sf "${VENV_DIR}/bin/converge" "${WRAPPER}"

  setup_path

  local ver
  ver="$("${VENV_DIR}/bin/python" -c 'from converge.version_info import package_version; print(package_version())')"
  info "Installed Converge ${ver}"
  info "Binary: ${WRAPPER}"
  info "Run: converge scan /path/to/your/repo"
}

main "$@"
