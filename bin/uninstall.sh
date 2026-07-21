#!/usr/bin/env bash
set -euo pipefail
usage() { echo "usage: uninstall.sh {opencode|codex|claude-code|cursor} [--force] [--install-root PATH]" >&2; }
[[ $# -ge 1 ]] || { usage; exit 2; }
platform=$1; shift
case "$platform" in opencode|codex|claude-code|cursor) ;; *) usage; exit 2;; esac
force=0
install_root=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force|-f) force=1; shift ;;
    --install-root) [[ $# -ge 2 ]] || { usage; exit 2; }; install_root=$2; shift 2 ;;
    *) usage; exit 2 ;;
  esac
done
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
args=(platform-uninstall --platform "$platform")
[[ -n "$install_root" ]] && args+=(--target-root "$install_root")
[[ $force -eq 1 ]] && args+=(--force)
exec "$root/bin/t-understand" "${args[@]}"
