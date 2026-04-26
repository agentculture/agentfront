# Agent-first CLI reference — integration guide

You (the agent) are reading this because someone ran `afi cli cite` against
their project. This folder contains the Python agent-first CLI pattern as a
reference — `{{tokens}}` are **not substituted**. Your job is to apply the
pattern to the host project on its own terms.

## Tokens

Substitute these throughout every file you integrate:

| Token             | Meaning                                    | Example        |
| ----------------- | ------------------------------------------ | -------------- |
| `{{project_name}}` | The published package / CLI name.          | `acme-tool`    |
| `{{slug}}`         | snake_case package slug (dashes→underscores). | `acme_tool`  |
| `{{module}}`       | Importable top-level module (same as slug).   | `acme_tool`  |

## File roles

### stable-contract — copy verbatim, then token-substitute

These files express the contract the rubric checks. Reshape them only if
your project already has equivalents; otherwise copy byte-for-byte.

- `{{slug}}/cli/_errors.py` — `AfiError`, exit-code policy.
- `{{slug}}/cli/_output.py` — stdout/stderr split + `--json` helpers.
- `{{slug}}/cli/_commands/explain.py` — the `explain` command.
- `{{slug}}/explain/__init__.py` + `{{slug}}/explain/catalog.py` — catalog resolver.

### shape-adapt — model the structure; rewrite to fit the host project

These show the target shape but will almost certainly be reshaped to match
the host project's existing module layout, prog name, and commands.

- `{{slug}}/cli/__init__.py` — the parser + `_dispatch`. Reuse the
  `_ArgumentParser` override and the try/except pattern verbatim; add your
  own noun groups in the marked location.
- `{{slug}}/cli/_commands/learn.py` — keep the structure (TEXT body + JSON
  payload) but rewrite the content to describe the host tool.
- `{{slug}}/explain/catalog.py` — rewrite entries for the host tool's
  commands; keep the `()` / `("{{project_name}}",)` alias pattern.
- `{{slug}}/__init__.py`, `{{slug}}/__main__.py` — usually already exist in
  the host project; update only if missing.
- `tests/test_cli.py` — merge into the host's test suite; adjust imports
  and the `{{project_name}}` literal expectations.

## Integration workflow (recommended)

1. Read `MANIFEST.json` for a machine-readable file inventory.
2. Copy the **stable-contract** files into the host project at the
   equivalent paths under the host's package. Substitute tokens.
3. Port the **shape-adapt** files: read them, take the structure, rewrite
   content to match the host's naming and command surface.
4. Wire the parser: import `learn` and `explain` modules and call their
   `register(sub)` functions in the host's argparse setup.
5. Ensure the host's top-level parser installs the `_ArgumentParser`
   override so unknown-verb errors emit with a `hint:` line.
6. Run `afi cli doctor .` from the host project to confirm the seven
   rubric bundles pass.

## Rubric bundles checked by `afi cli doctor`

1. **Structure** — `pyproject.toml` with `[project.scripts]`, `tests/` dir,
   `<tool> --help` exits 0, `main(argv) -> int` signature conforms.
2. **Learnability** — `<tool> learn` exits 0, stdout ≥ 200 chars,
   mentions purpose, commands, exit codes, `--json`, `explain`.
3. **JSON** — `<tool> learn --json` is parseable; stderr clean on success;
   `<tool> explain --json` works.
4. **Errors** — bogus verb exits non-zero with a `hint:` line and no
   Python traceback.
5. **Explain** — `explain`, `explain <tool>`, and bogus-path-failure with
   hint all work.
6. **Overview** — `<tool> overview` and `<tool> cli overview` succeed;
   `overview --json` carries `subject` + `sections` keys; missing target
   paths fall back gracefully (descriptive verbs do not hard-fail).
7. **Doctor** — `<tool> doctor` produces a non-empty report;
   `<tool> doctor --json` carries `healthy` (bool) + `checks` (list);
   each check entry has `id`, `passed`, `severity`, `message`; failed
   checks supply a non-empty `remediation`.

> Note: this reference tree currently scaffolds `learn` and `explain` only.
> A target CLI must also implement `overview` (bundle 6) and `doctor`
> (bundle 7) to pass the full rubric. Use afi's own implementations as
> templates: `afi explain overview` and `afi explain doctor` describe the
> contract; the source under `afi/overview/` and `afi/doctor/` shows the
> shape. (Tracked: ship `overview.py` and `doctor.py` reference templates
> in a follow-up cite refresh.)

## After integration

Delete this reference (`rm -rf .afi/reference/`) or re-run `afi cli cite` to
refresh it. The `.afi/` entry in `.gitignore` keeps it out of commits.

## Rubric audit verb

Run `afi cli doctor .` from the host project to confirm the seven rubric
bundles pass. `afi cli verify` is a deprecated alias for the same command
and will be removed in v0.6.0.
