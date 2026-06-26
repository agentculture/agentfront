"""Self-doctor checks for an installed ``agentfront``.

Every check is in-process and side-effect free. Heavy work (subprocess
probes, network, target audits) is the rubric runner's job under
``agentfront cli doctor <path>``; ``agentfront doctor`` is the cheap, deterministic
self-survey an agent can run before doing real work.

Checks emit :class:`CheckResult` with ``bundle="self"``. Failures carry a
``remediation`` string; none are currently ``auto_fixable=True`` because
the safe fixes for an installed agentfront (re-installing a corrupt wheel,
editing source) cannot be applied from inside a doctor run. The
``fix_id`` field is reserved for follow-up auto-fix handlers.
"""

from __future__ import annotations

import argparse
import tomllib
from pathlib import Path

import agentfront
from agentfront import __version__, _brand
from agentfront.cli import _build_parser
from agentfront.cli._commands.learn import _as_json_payload
from agentfront.explain import resolve as explain_resolve
from agentfront.rubric import default_rubric
from agentfront.rubric._types import CheckResult

BUNDLE = "self"


def _find_repo_root() -> Path | None:
    """Locate the agentfront source repo by walking up from the package.

    Returns ``None`` when running from an installed wheel (the package is
    inside ``site-packages`` and no ``pyproject.toml`` for ``agentfront`` is
    findable upward). Self-checks that only matter at dev time degrade to
    ``info`` severity in that case.
    """
    p = Path(agentfront.__file__).resolve().parent
    while p != p.parent:
        candidate = p / "pyproject.toml"
        if candidate.is_file():
            try:
                data = tomllib.loads(candidate.read_text())
            except (OSError, tomllib.TOMLDecodeError):
                p = p.parent
                continue
            project = data.get("project") if isinstance(data, dict) else None
            if isinstance(project, dict) and project.get("name") in (
                _brand.DIST,
                _brand.LEGACY_DIST,
            ):
                return p
        p = p.parent
    return None


def _argparse_leaf_paths(
    parser: argparse.ArgumentParser, prefix: tuple[str, ...] = ()
) -> list[tuple[str, ...]]:
    """Walk the parser tree and return tuples for every leaf verb.

    A leaf is a parser that has no nested subparsers — i.e. an actual
    invocable verb. Nouns (``cli``) are not leaves, so they are absent
    from the returned list.
    """
    leaves: list[tuple[str, ...]] = []
    has_subparser = False
    for action in parser._actions:  # noqa: SLF001 - argparse has no public iterator
        if isinstance(action, argparse._SubParsersAction):
            has_subparser = True
            for name, subparser in action.choices.items():
                leaves.extend(_argparse_leaf_paths(subparser, prefix + (name,)))
    if not has_subparser and prefix:
        leaves.append(prefix)
    return leaves


def _check_version_consistency() -> CheckResult:
    repo = _find_repo_root()
    if repo is None:
        return CheckResult(
            BUNDLE,
            "version_consistency",
            True,
            "info",
            f"installed wheel; version from importlib.metadata = {__version__}",
        )
    pyproject = repo / "pyproject.toml"
    try:
        data = tomllib.loads(pyproject.read_text())
    except (OSError, tomllib.TOMLDecodeError) as err:
        return CheckResult(
            BUNDLE,
            "version_consistency",
            False,
            "error",
            f"could not parse {pyproject}: {err}",
            remediation="fix the TOML syntax error in pyproject.toml",
        )
    project = data.get("project") if isinstance(data, dict) else None
    if project is not None and not isinstance(project, dict):
        return CheckResult(
            BUNDLE,
            "version_consistency",
            False,
            "error",
            f"invalid {pyproject}: [project] must be a TOML table",
            remediation=(
                "rewrite the [project] section as a table per PEP 621 "
                "(https://peps.python.org/pep-0621/)"
            ),
        )
    declared = project.get("version") if isinstance(project, dict) else None
    if declared == __version__:
        return CheckResult(
            BUNDLE,
            "version_consistency",
            True,
            "info",
            f"pyproject.version == importlib.metadata.version == {__version__}",
        )
    return CheckResult(
        BUNDLE,
        "version_consistency",
        False,
        "error",
        f"pyproject={declared!r} but importlib.metadata={__version__!r}",
        remediation=(
            "re-run `uv sync` so the editable install picks up the new pyproject "
            "version, or use the version-bump skill to keep both in sync"
        ),
    )


def _check_changelog_entry() -> CheckResult:
    repo = _find_repo_root()
    if repo is None:
        return CheckResult(
            BUNDLE,
            "changelog_entry",
            True,
            "info",
            "installed wheel ships no CHANGELOG; check skipped",
        )
    changelog = repo / "CHANGELOG.md"
    if not changelog.is_file():
        return CheckResult(
            BUNDLE,
            "changelog_entry",
            False,
            "warn",
            f"no CHANGELOG.md at {changelog}",
            remediation=(
                "create CHANGELOG.md following Keep a Changelog format; the "
                "version-bump skill prepends entries automatically"
            ),
        )
    text = changelog.read_text()
    needle = f"[{__version__}]"
    if needle in text:
        return CheckResult(
            BUNDLE,
            "changelog_entry",
            True,
            "info",
            f"CHANGELOG.md has an entry for [{__version__}]",
        )
    return CheckResult(
        BUNDLE,
        "changelog_entry",
        False,
        "warn",
        f"CHANGELOG.md has no [{__version__}] heading",
        remediation=(
            f"prepend a Keep-a-Changelog entry for {__version__} via "
            "`python3 .claude/skills/version-bump/scripts/bump.py` "
            "(use --help for the JSON-on-stdin contract)"
        ),
    )


def _check_surface_coherence_learn() -> CheckResult:
    parser = _build_parser()
    leaves = {tuple(p) for p in _argparse_leaf_paths(parser)}
    learn_paths = {tuple(c["path"]) for c in _as_json_payload()["commands"]}
    missing = sorted(leaves - learn_paths)
    if not missing:
        return CheckResult(
            BUNDLE,
            "surface_coherence_learn",
            True,
            "info",
            f"every argparse leaf ({len(leaves)} verbs) appears in `learn --json`",
        )
    rendered = ", ".join(" ".join(p) for p in missing)
    return CheckResult(
        BUNDLE,
        "surface_coherence_learn",
        False,
        "error",
        f"argparse leaves missing from learn payload: {rendered}",
        remediation=(
            "add the missing verbs to `_as_json_payload()` in agentfront/cli/_commands/learn.py "
            "and to the prose `_TEXT` block; otherwise an agent reading `learn --json` "
            "cannot discover those verbs"
        ),
    )


def _check_surface_coherence_explain() -> CheckResult:
    parser = _build_parser()
    leaves = _argparse_leaf_paths(parser)
    missing: list[str] = []
    for path in leaves:
        try:
            explain_resolve(path)
        except Exception:  # noqa: BLE001 - resolve raises AgentfrontError; treat any miss the same
            missing.append(" ".join(path))
    if not missing:
        return CheckResult(
            BUNDLE,
            "surface_coherence_explain",
            True,
            "info",
            f"every argparse leaf ({len(leaves)} verbs) resolves via agentfront.explain",
        )
    return CheckResult(
        BUNDLE,
        "surface_coherence_explain",
        False,
        "error",
        f"missing explain entries: {', '.join(missing)}",
        remediation=(
            "add markdown bodies to agentfront/explain/catalog.py keyed on the verb path "
            "(e.g. ('cli', 'doctor')); without an entry `agentfront explain <verb>` fails "
            "and the rubric's explain bundle regresses"
        ),
    )


def _check_rubric_modules_loadable() -> CheckResult:
    bundles = default_rubric()
    bad: list[str] = []
    for module in bundles:
        name = getattr(module, "__name__", repr(module))
        checks = getattr(module, "CHECKS", None)
        run = getattr(module, "run", None)
        if not isinstance(checks, list) or not checks:
            bad.append(f"{name} (no CHECKS list)")
            continue
        if not callable(run):
            bad.append(f"{name} (no callable run)")
    if bad:
        return CheckResult(
            BUNDLE,
            "rubric_modules_loadable",
            False,
            "error",
            f"malformed rubric bundles: {', '.join(bad)}",
            remediation=(
                "every bundle module must export a non-empty CHECKS list and a "
                "callable run(ctx) — see existing bundles under agentfront/rubric/checks/"
            ),
        )
    return CheckResult(
        BUNDLE,
        "rubric_modules_loadable",
        True,
        "info",
        f"all {len(bundles)} rubric bundles loadable with non-empty CHECKS",
    )


CHECKS = [
    _check_version_consistency,
    _check_changelog_entry,
    _check_surface_coherence_learn,
    _check_surface_coherence_explain,
    _check_rubric_modules_loadable,
]


def run_self_checks() -> list[CheckResult]:
    """Run every self-check in order and return the flat result list."""
    return [check() for check in CHECKS]
