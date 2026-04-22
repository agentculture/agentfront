---
name: lint-markdown
description: Use after editing any .md file in this repo, before committing, or when the pre-commit hook rejects a commit with markdownlint errors. Runs the repo lint script which auto-fixes violations.
---

# Lint markdown

One step: run the repo script.

```
scripts/lint-md.sh
```

No flags. It handles file selection (all tracked `.md` files), auto-fix, and config resolution.

To scope to specific files, pass them as arguments:

```
scripts/lint-md.sh path/to/file.md path/to/other.md
```

## If violations remain after the script runs

`markdownlint-cli2 --fix` cannot repair every rule (e.g. MD013 line-length, MD024 duplicate headings). For anything left:

1. Read the reported file:line — the output is `path:line:col rule description`.
2. Fix with `Edit`, targeting the exact line.
3. Re-run `scripts/lint-md.sh` to confirm zero violations.
4. Re-stage the fixed files before committing.
