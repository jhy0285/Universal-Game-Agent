#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
.venv/bin/ruff check .
.venv/bin/python -m pytest --junitxml=.uga/test-results.xml
.venv/bin/uga benchmark --output .uga/benchmark-validation
