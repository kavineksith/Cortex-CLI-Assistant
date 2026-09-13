#!/usr/bin/env bash
# scripts/install.sh
# Sets up a virtual environment and installs dependencies for the
# Cortex CLI Assistant. Safe to re-run (idempotent).
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

echo "==> Cortex CLI Assistant installer"

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 is required but was not found on PATH." >&2
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
REQUIRED="3.10"
if [ "$(printf '%s\n' "$REQUIRED" "$PY_VERSION" | sort -V | head -n1)" != "$REQUIRED" ]; then
    echo "ERROR: Python ${REQUIRED}+ is required, found ${PY_VERSION}." >&2
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "==> Creating virtual environment at ${VENV_DIR}"
    python3 -m venv "$VENV_DIR"
else
    echo "==> Reusing existing virtual environment"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

echo "==> Upgrading pip"
pip install --upgrade pip >/dev/null

echo "==> Installing dependencies"
pip install -r "${PROJECT_ROOT}/requirements.txt"

mkdir -p "${PROJECT_ROOT}/logs"

echo "==> Done. Activate with: source ${VENV_DIR}/bin/activate"
echo "==> Then run:            python main.py run"
