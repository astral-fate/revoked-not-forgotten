#!/usr/bin/env bash
# Regenerate every number, table and Figure 2 from the trial records, then compile main.pdf.
set -euo pipefail
cd "$(dirname "$0")"
python make_numbers.py
python make_ext.py
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
