"""agentfront dogfoods its own runtime.

It builds an :class:`App` from agentfront's *own* docs + a tool and serves all
three surfaces from it — the exact round-trip a host package gets from
``import agentfront``, proven against agentfront itself. Run as a CI gate::

    python -m agentfront._dogfood

Exits non-zero if the three surfaces disagree or the runtime doctor is unhealthy.
"""

from __future__ import annotations

import sys
from pathlib import Path

from agentfront import App, __version__
from agentfront.doctor_live import healthy, run_doctor
from agentfront.serve import surface_inventory, surfaces_agree
from agentfront.taui.diagnose import diagnose

# The hand-written guide docs (not the generated specs/plans or Jekyll partials).
_GUIDE_DOCS = ("agentculture", "agent-first", "rubric", "skill-sources")


def build_app() -> App:
    """Construct the App that represents agentfront itself."""
    app = App(
        name="agentfront",
        version=__version__,
        description="Agent First Interface runtime — one config, three surfaces.",
    )
    docs_dir = Path(__file__).resolve().parent.parent / "docs"
    for slug in _GUIDE_DOCS:
        md = docs_dir / f"{slug}.md"
        if md.is_file():
            app.add_doc(slug=slug, title=slug.replace("-", " ").title(), path=str(md))
    if not app.list_docs():
        # installed without the source docs/ tree — still serve something real
        app.add_doc(
            slug="about",
            title="About agentfront",
            text=(
                "# agentfront\n\nAgent First Interface runtime: import, configure, "
                "and serve CLI + MCP + HTTP from one source of truth."
            ),
        )

    @app.tool
    def version() -> str:
        """Return the running agentfront version."""
        return __version__

    return app


# Module-level App so `from agentfront._dogfood import app` works like any host.
app = build_app()


def main() -> int:
    """Boot all four surfaces and assert they agree — the dogfood CI gate."""
    a = build_app()
    # building each surface must not raise
    a.http_app()
    a.mcp_server()
    a.cli()
    a.taui()
    inv = surface_inventory(a)
    checks = run_doctor(a)
    agree = surfaces_agree(a)
    diag = diagnose(a.taui())
    print(
        f"agentfront {a.version}: {len(inv['registry_docs'])} docs, "
        f"{len(inv['registry_tools'])} tools"
    )
    print(f"  surfaces_agree: {agree}")
    for check in checks:
        print(f"  doctor[{check.name}]: {check.status}")
    print(f"  taui_diagnose: {diag.ok}")
    if not (agree and healthy(checks) and diag.ok):
        print("DOGFOOD FAILED: surfaces disagree or doctor unhealthy", file=sys.stderr)
        return 1
    print("DOGFOOD OK: agentfront serves its own four surfaces, and they agree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
