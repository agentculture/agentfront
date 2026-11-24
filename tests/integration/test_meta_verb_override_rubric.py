"""End to end: a tiny app that overrides meta-verbs still passes the rubric.

The app uses only public API: ``App.meta_verb`` for ``explain``, ``overview``
and ``doctor``, ``App.add_learn_section`` for ``learn`` (which is extended,
never replaced), and ``App.run_cli`` as its ``main``. The seven-bundle rubric
then runs against it through an in-process runner that calls ``run_cli``, so
the checks see exactly what a subprocess would (exit code, stdout, stderr).

One structure check, ``main_entry_contract``, shells out to ``uv run`` inside
the target project to import its entry point. The throwaway project here is
not an installable package, so that check is skipped and its invariant
(``main(argv) -> int``, no ``SystemExit`` on ``--help``) is asserted directly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from agentfront import App
from agentfront.errors import EXIT_USER_ERROR, AgentfrontError
from agentfront.rubric import default_rubric
from agentfront.rubric._types import RunOutput, VerifyContext
from agentfront.rubric.checks import structure
from agentfront.serve import surfaces_agree
from agentfront.testing import run_cli as harness_run_cli

CATALOG = {
    (): "# tiny\n\nA tiny tool that overrides its meta-verbs.\n",
    ("tiny",): "# tiny\n\nA tiny tool that overrides its meta-verbs.\n",
    ("greet",): "# greet\n\nSay hello to someone.\n",
}


def build_app() -> App:
    app = App(name="tiny", version="0.1.0", description="A tiny tool with its own meta-verbs.")
    app.add_doc(slug="tiny", title="tiny", text=CATALOG[()])

    @app.tool(doc=CATALOG[("greet",)])
    def greet(name: str) -> str:
        """Say hello to someone."""
        return f"hello {name}"

    @app.tool(name="overview", group="cli")
    def cli_overview() -> str:
        """Describe the CLI surface."""
        return "tiny CLI: greet, learn, explain, overview, doctor"

    app.add_learn_section("Runtime", "tiny runs entirely in-process; it needs no daemon.")

    @app.meta_verb("explain")
    def explain(args: argparse.Namespace) -> int:
        path = tuple(args.path)
        if path not in CATALOG:
            raise AgentfrontError(
                code=EXIT_USER_ERROR,
                message=f"no such path: {' '.join(path)}",
                remediation="run 'tiny overview' to list valid paths",
            )
        text = CATALOG[path]
        print(json.dumps({"path": list(path), "markdown": text}) if args.json else text)
        return 0

    @app.meta_verb("overview")
    def overview(args: argparse.Namespace) -> int:
        sections = [{"title": "Verbs", "items": ["greet", "cli overview"]}]
        if args.json:
            print(json.dumps({"subject": "tiny", "sections": sections}))
        else:
            print("# tiny\n\n## Verbs\n- greet\n- cli overview")
        return 0  # descriptive: an unknown scope is ignored, never a hard failure

    @app.meta_verb("doctor")
    def doctor(args: argparse.Namespace) -> int:
        checks = [
            {
                "id": "identity",
                "passed": True,
                "severity": "error",
                "message": "project identity is consistent",
                "remediation": "",
            }
        ]
        healthy = all(c["passed"] for c in checks)
        if args.json:
            print(json.dumps({"healthy": healthy, "checks": checks}))
        else:
            print(f"tiny doctor: {'healthy' if healthy else 'unhealthy'}")
        return 0 if healthy else 1

    return app


def main(argv: list[str] | None = None) -> int:
    return build_app().run_cli(argv)


class InProcessRunner:
    """A rubric ``Runner`` that drives ``App.run_cli`` in-process."""

    def __init__(self, app: App) -> None:
        self._app = app

    def run(self, args: list[str], *, timeout: float = 10.0) -> RunOutput:
        del timeout
        result = harness_run_cli(self._app, list(args))
        return RunOutput(result.exit_code, result.stdout, result.stderr)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "tiny"\nversion = "0.1.0"\n\n[project.scripts]\ntiny = "tiny:main"\n',
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir()
    return tmp_path


def test_overriding_app_passes_every_rubric_bundle(project: Path) -> None:
    ctx = VerifyContext(target_path=project, tool_name="tiny", runner=InProcessRunner(build_app()))
    results = []
    bundles = set()
    for bundle in default_rubric():
        for check in bundle.CHECKS:
            if check is structure._check_main_entry_contract:
                continue  # needs an installable project; asserted directly below
            result = check(ctx)
            results.append(result)
            bundles.add(result.bundle)

    assert bundles == {
        "structure",
        "learnability",
        "json",
        "errors",
        "explain",
        "overview",
        "doctor",
    }
    # --strict semantics: no failure of any severity.
    failures = [r for r in results if not r.passed]
    assert not failures, "\n".join(
        f"[{r.bundle}] {r.check} ({r.severity}): {r.evidence} hint: {r.remediation}"
        for r in failures
    )


def test_main_entry_contract_holds(capsys) -> None:
    assert main(["--help"]) == 0
    assert main(["--version"]) == 0
    assert "tiny 0.1.0" in capsys.readouterr().out
    assert main(["greet", "ada"]) == 0
    assert main(["no-such-verb"]) == 1


def test_overriding_app_surfaces_still_agree() -> None:
    assert surfaces_agree(build_app())


def test_learn_section_and_inventory_both_present() -> None:
    app = build_app()
    text = harness_run_cli(app, ["learn"]).stdout
    assert "## Runtime" in text and "greet" in text
    payload = json.loads(harness_run_cli(app, ["learn", "--json"]).stdout)
    assert ["greet"] in [t["path"] for t in payload["tools"]]
    assert payload["sections"][0]["title"] == "Runtime"
