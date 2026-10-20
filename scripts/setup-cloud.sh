#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
uga_python=""
for uga_candidate in python3.11 python3.12; do
  if command -v "$uga_candidate" >/dev/null 2>&1; then
    uga_python="$(command -v "$uga_candidate")"
    break
  fi
done
if [[ -z "$uga_python" ]]; then
  echo 'UGA requires an installed Python 3.11 or 3.12 interpreter.' >&2
  exit 1
fi
command -v uv >/dev/null
uv sync --frozen --python "$uga_python" --no-python-downloads
.venv/bin/uga doctor
