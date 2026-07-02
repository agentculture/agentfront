"""End-to-end consumer-App test (t13 finale).

Builds ONE example consumer App purely by registration and asserts the
CONJUNCTION of all success signals:

  - run_cli dispatches a nested verb with parsed typed args
  - per-verb --json: success → JSON stdout; AgentfrontError → JSON stderr + nonzero
  - host add_command launcher verb is invocable alongside generated verbs
  - explain <path> returns the op's doc; overview lists nouns; learn enumerates ops
  - the SAME app yields mcp_server() (single-dispatch) and http_app()
  - assert_surfaces_agree(app) passes
  - BEFORE→AFTER contrast: empty App exposes only learn/doctor; populated App
    exposes the full nested tree
"""

from __future__ import annotations

import json
from typing import Any

from agentfront import App
from agentfront._registry import Flag
from agentfront.cli_surface import run_cli
from agentfront.errors import AgentfrontError
from agentfront.testing import assert_surfaces_agree
from agentfront.testing import run_cli as harness_run_cli

# ---------------------------------------------------------------------------
# Build the consumer App purely by registration
# ---------------------------------------------------------------------------


def _build_app() -> App:
    """A consumer App with >=2-level nesting, custom flags, and a host command."""
    app = App(name="consumer", version="1.0.0", description="E2E consumer app")

    # --- Level-1 group: "data" with verbs --------------------------------
    @app.tool(group="data")
    def create(name: str, value: int = 0) -> str:
        """Create a data entry."""
        return f"created {name}={value}"

    @app.tool(group="data")
    def delete(key: str) -> str:
        """Delete a data entry."""
        return f"deleted {key}"

    # --- Level-2 nested group: "data transform" with verbs ----------------
    @app.tool(group=("data", "transform"))
    def encode(payload: str) -> str:
        """Encode a payload."""
        return f"encoded:{payload}"

    @app.tool(group=("data", "transform"))
    def decode(token: str) -> str:
        """Decode a token."""
        return f"decoded:{token}"

    # --- Verb with custom Flag declarations ------------------------------
    @app.tool(
        group="data",
        flags=(
            Flag(names=("--verbose", "-v"), action="store_true", default=False),
            Flag(names=("--format", "-f"), default="json", help="output format"),
        ),
    )
    def export(target: str) -> str:
        """Export data to a target."""
        return f"exported {target}"

    # --- Verb that raises AgentfrontError --------------------------------
    @app.tool(group="data")
    def fail() -> None:
        """Always fail."""
        raise AgentfrontError(
            code=1,
            message="intentional failure",
            remediation="this is expected",
        )

    # --- Host-owned launcher verb (NOT a @app.tool) ----------------------
    def launcher_handler(args: Any) -> int:
        """Host-owned launcher — registered via add_command."""
        print("launcher: running")
        return 0

    app.add_command("launch", launcher_handler, help="host-owned launcher")

    return app


# ---------------------------------------------------------------------------
# Tests: the conjunction of success signals
# ---------------------------------------------------------------------------


class TestNestedDispatch:
    """run_cli dispatches nested verbs with parsed typed args."""

    def test_level1_verb_dispatches(self, capsys) -> None:
        app = _build_app()
        rc = run_cli(app, ["data", "create", "hello", "--value", "42"])
        assert rc == 0
        assert "created hello=42" in capsys.readouterr().out

    def test_level2_nested_verb_dispatches(self, capsys) -> None:
        app = _build_app()
        rc = run_cli(app, ["data", "transform", "encode", "payload"])
        assert rc == 0
        assert "encoded:payload" in capsys.readouterr().out

    def test_level2_decode_dispatches(self, capsys) -> None:
        app = _build_app()
        rc = run_cli(app, ["data", "transform", "decode", "token"])
        assert rc == 0
        assert "decoded:token" in capsys.readouterr().out


class TestJsonMode:
    """Per-verb --json: success → JSON stdout; error → JSON stderr + nonzero."""

    def test_verb_json_success(self, capsys) -> None:
        app = _build_app()
        rc = run_cli(app, ["data", "create", "x", "--value", "1", "--json"])
        assert rc == 0
        captured = capsys.readouterr()
        payload = json.loads(captured.out.strip())
        assert payload == "created x=1"

    def test_verb_error_json_stderr(self, capsys) -> None:
        app = _build_app()
        rc = run_cli(app, ["data", "fail", "--json"])
        assert rc == 1
        captured = capsys.readouterr()
        payload = json.loads(captured.err.strip())
        assert payload["code"] == 1
        assert payload["message"] == "intentional failure"
        assert payload["remediation"] == "this is expected"
        assert captured.out == ""

    def test_verb_error_text_stderr(self, capsys) -> None:
        app = _build_app()
        rc = run_cli(app, ["data", "fail"])
        assert rc == 1
        captured = capsys.readouterr()
        assert "intentional failure" in captured.err
        assert captured.out == ""


class TestHostCommand:
    """The host add_command launcher verb is invocable alongside generated verbs."""

    def test_host_launcher_invocable(self, capsys) -> None:
        app = _build_app()
        rc = run_cli(app, ["launch"])
        assert rc == 0
        assert "launcher: running" in capsys.readouterr().out

    def test_host_and_generated_coexist(self, capsys) -> None:
        """Both host command and generated verb work in the same app."""
        app = _build_app()
        rc1 = run_cli(app, ["launch"])
        assert rc1 == 0
        rc2 = run_cli(app, ["data", "create", "y", "--value", "2"])
        assert rc2 == 0
        out = capsys.readouterr().out
        assert "created y=2" in out


class TestRegistryMetaVerbs:
    """explain, overview, learn are registry-derived."""

    def test_explain_returns_op_doc(self, capsys) -> None:
        app = _build_app()
        rc = run_cli(app, ["explain", "data", "create"])
        assert rc == 0
        assert "Create a data entry" in capsys.readouterr().out

    def test_explain_nested_path(self, capsys) -> None:
        app = _build_app()
        rc = run_cli(app, ["explain", "data", "transform", "encode"])
        assert rc == 0
        assert "Encode a payload" in capsys.readouterr().out

    def test_explain_json(self, capsys) -> None:
        app = _build_app()
        rc = run_cli(app, ["explain", "data", "create", "--json"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out.strip())
        assert payload["path"] == ["data", "create"]
        assert "Create a data entry" in payload["doc"]

    def test_overview_lists_nouns(self, capsys) -> None:
        app = _build_app()
        rc = run_cli(app, ["overview"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "data" in out

    def test_overview_json(self, capsys) -> None:
        app = _build_app()
        rc = run_cli(app, ["overview", "--json"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out.strip())
        assert isinstance(payload, list)

    def test_learn_enumerates_ops(self, capsys) -> None:
        app = _build_app()
        rc = run_cli(app, ["learn"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "data" in out
        assert "create" in out

    def test_learn_json(self, capsys) -> None:
        app = _build_app()
        rc = run_cli(app, ["learn", "--json"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out.strip())
        assert payload["name"] == "consumer"
        assert isinstance(payload["tools"], list)
        # At least the nested tools are present
        tool_paths = {"/".join(t["path"]) for t in payload["tools"]}
        assert "data/create" in tool_paths
        assert "data/transform/encode" in tool_paths


class TestSurfaces:
    """The SAME app yields mcp_server() and http_app(); surfaces agree."""

    def test_mcp_server_single_dispatch(self) -> None:
        app = _build_app()
        server = app.mcp_server()
        assert server is not None

        async def _list():
            from mcp import types

            handler = server.request_handlers[types.ListToolsRequest]
            req = types.ListToolsRequest(
                method="tools/list",
                params=types.PaginatedRequestParams(cursor=None),
            )
            result = await handler(req)
            return {t.name for t in result.root.tools}

        import anyio

        tool_names = anyio.run(_list)
        # Single-dispatch: exactly one 'run' tool
        assert tool_names == {"run"}

    def test_http_app_serves_doc(self) -> None:
        app = _build_app()
        app.add_doc(slug="intro", title="Intro", text="# Intro\nhello")
        wsgi = app.http_app()
        environ = {"REQUEST_METHOD": "GET", "PATH_INFO": "/intro"}
        body = b"".join(wsgi(environ, lambda s, h: None))
        assert b"# Intro" in body

    def test_surfaces_agree(self) -> None:
        app = _build_app()
        app.add_doc(slug="intro", title="Intro", text="# Intro\nhello")
        assert_surfaces_agree(app)


class TestBeforeAfterContrast:
    """A fresh App with NO tools exposes only learn/doctor; populated App
    exposes the full nested tree."""

    def test_empty_app_meta_verbs_only(self, capsys) -> None:
        """An empty App exposes learn and doctor (the old shape)."""
        app = App(name="empty", version="0.1")
        rc = run_cli(app, ["learn"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "empty" in out

        rc = run_cli(app, ["doctor"])
        assert rc == 0

    def test_empty_app_no_tools_in_learn(self, capsys) -> None:
        """An empty App's learn output has no tools."""
        app = App(name="empty", version="0.1")
        rc = run_cli(app, ["learn", "--json"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out.strip())
        assert payload["tools"] == []

    def test_populated_app_full_tree(self, capsys) -> None:
        """The populated App exposes the full nested tree (the new shape)."""
        app = _build_app()
        rc = run_cli(app, ["learn", "--json"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out.strip())
        tool_paths = {"/".join(t["path"]) for t in payload["tools"]}
        # The populated app has nested tools the empty one doesn't
        assert "data/create" in tool_paths
        assert "data/transform/encode" in tool_paths
        assert "data/transform/decode" in tool_paths
        assert "data/export" in tool_paths
        assert "data/fail" in tool_paths
        assert "data/delete" in tool_paths

    def test_empty_vs_populated_contrast(self) -> None:
        """Explicit BEFORE→AFTER: empty has 0 tools, populated has many."""
        empty = App(name="empty", version="0.1")
        populated = _build_app()

        assert len(empty.list_tools()) == 0
        assert len(populated.list_tools()) >= 6

        # learn --json reflects the difference
        empty_payload = json.loads(harness_run_cli(empty, ["learn", "--json"]).stdout)
        pop_payload = json.loads(harness_run_cli(populated, ["learn", "--json"]).stdout)

        assert len(empty_payload["tools"]) == 0
        assert len(pop_payload["tools"]) >= 6
