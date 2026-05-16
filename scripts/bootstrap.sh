#!/bin/zsh
# Create/update the repo-owned Python runtime used by all services.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="${PROJECT_DIR}/.venv"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"

echo "Creating Python runtime at ${VENV_DIR}"
"${PYTHON_BIN}" -m venv "${VENV_DIR}"

echo "Installing pinned dependencies"
"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install -r "${PROJECT_DIR}/requirements.txt"

mkdir -p "${PROJECT_DIR}/logs" "${PROJECT_DIR}/output/pending" "${PROJECT_DIR}/output/approved"

echo "Running doctor"
"${VENV_DIR}/bin/python" "${PROJECT_DIR}/scripts/doctor.py" || true

echo "Bootstrap complete. Runtime: ${VENV_DIR}/bin/python"
