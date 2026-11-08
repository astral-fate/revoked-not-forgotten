#!/usr/bin/env bash
# Tables (Wilson 95% CIs), exact McNemar tests and Figure 1 over every experiment's results.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$HERE/../../src"
python -m revres.analyze "$HERE"/../0*/results/*/ --out "$HERE"
