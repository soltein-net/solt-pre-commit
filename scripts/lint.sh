#!/usr/bin/env bash
# Single source of truth for lint/format checks - run identically by
# `ci.yml` (lint job) and by developers locally, so a push never surfaces
# a failure that couldn't have been caught before pushing.
#
# Usage:
#   scripts/lint.sh          # check only (what CI runs) - exits non-zero on violations
#   scripts/lint.sh --fix    # apply ruff's autofixes and reformat in place
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -d "solt_pre_commit" ]; then
  TARGET="solt_pre_commit/"
elif [ -d "src/solt_pre_commit" ]; then
  TARGET="src/solt_pre_commit/"
else
  TARGET="."
fi

if [ "${1:-}" = "--fix" ]; then
  ruff check "$TARGET" --ignore E501 --fix
  ruff format "$TARGET"
else
  ruff check "$TARGET" --ignore E501
  ruff format --check "$TARGET"
fi
