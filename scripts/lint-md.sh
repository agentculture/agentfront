#!/usr/bin/env bash
# Lint and auto-fix markdown in this repo.
#
# Usage:
#   scripts/lint-md.sh           # lint & fix all tracked .md files
#   scripts/lint-md.sh FILE ...  # lint & fix specific files
#
# Config resolution (markdownlint-cli2 built-in): repo-local
# .markdownlint-cli2.{jsonc,yaml,cjs} if present, else ~/.markdownlint-cli2.yaml.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

if [ $# -eq 0 ]; then
  mapfile -t files < <(git ls-files '*.md')
  if [ ${#files[@]} -eq 0 ]; then
    echo "No tracked markdown files."
    exit 0
  fi
  set -- "${files[@]}"
fi

exec markdownlint-cli2 --fix "$@"
