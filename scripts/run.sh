#!/usr/bin/env bash
# scripts/run.sh
# Convenience launcher. Forwards all arguments to main.py, e.g.:
#   ./scripts/run.sh run
#   ./scripts/run.sh add-task "Buy milk" --priority high
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

if [ -d "$VENV_DIR" ]; then
    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate"
fi

cd "$PROJECT_ROOT"
exec python3 main.py "$@"
