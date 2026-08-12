#!/usr/bin/env bash
# Bootstrap Bug Archaeology from a fresh clone.
#   ./bootstrap.sh
set -euo pipefail

CORPUS_REPO="https://github.com/psf/requests.git"
# Deliberately OUTSIDE this repo (Phase 0 decision) so a 6,500-commit corpus
# never lands in bug-archaeology's own git history.
CORPUS_DIR="../corpus/requests"

echo "==> [1/5] Checking for uv"
if ! command -v uv &> /dev/null; then
    echo "    uv not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

echo "==> [2/5] Creating virtual environment (Python 3.11)"
uv venv --python 3.11

echo "==> [3/5] Installing dependencies"
uv pip install -e ".[dev]"

echo "==> [4/5] Installing git hooks"
.venv/bin/pre-commit install

echo "==> [5/5] Cloning corpus: $CORPUS_REPO -> $CORPUS_DIR"
if [ -d "$CORPUS_DIR/.git" ]; then
    echo "    Already present, pulling latest."
    git -C "$CORPUS_DIR" pull --ff-only
else
    mkdir -p "$(dirname "$CORPUS_DIR")"
    git clone "$CORPUS_REPO" "$CORPUS_DIR"
fi

echo ""
echo "==> Verifying"
.venv/bin/pytest -q

echo ""
echo "Done. Activate with:  source .venv/bin/activate"
