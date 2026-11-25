#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python scripts/sanitize_snapshots.py
python scripts/build_catalog.py
python scripts/validate_catalog.py
python scripts/render_markdown.py
if [[ -x .venv/bin/mkdocs ]]; then
  .venv/bin/mkdocs build --strict
else
  mkdocs build --strict
fi
