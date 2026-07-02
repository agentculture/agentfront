"""Public TAUI testing helpers — drive a scripted event trail, assert parity.

These helpers complete the ``agentfront.testing`` harness for the TAUI
surface: :func:`drive` scripts a mixed agent/human event list through a fresh
:class:`~agentfront.taui.session.Session` (executing real tools for
``SelectorAction`` events, exactly like :meth:`Session.dispatch` does for a
live agent); :func:`assert_agent_human_parity` proves the agent's
selector-dispatch path and the human's down-key navigation path land on the
same state for the same destination; :func:`assert_replay_equivalent` proves
a session's own event trail, replayed from its own starting state, reproduces
its own current state — the "the trail is the ground truth" invariant
:class:`Session` is built on.

The snapshot quad (``write_snapshot``, ``read_snapshot``, ``Snapshot``) and
``replay`` are re-exported here eagerly, so a consumer test suite only ever
needs one import line (``from agentfront.testing import ...``). ``resume``
(``agentfront.taui.snapshot.resume``) is re-exported LAZILY via a
module-level ``__getattr__`` (PEP 562): a sibling task adds ``resume`` to
``agentfront.taui.snapshot`` independently, so importing this module must not
hard-fail while that lands — the attribute simply becomes available the first
time it is accessed, once the sibling module has it.
"""

from __future__ import annotations

from typing import Any

from agentfront.app import App
from agentfront.taui.events import Event, SelectorAction
from agentfront.taui.reducer import focus_order, replay
from agentfront.taui.session import Session
from agentfront.taui.snapshot import Snapshot, read_snapshot, write_snapshot

__all__ = [  # noqa: F822 — "resume" is a lazy PEP 562 attribute, resolved by __getattr__ below
    "drive",
    "assert_agent_human_parity",
    "assert_replay_equivalent",
    "write_snapshot",
    "read_snapshot",
    "replay",
    "Snapshot",
    "resume",
]


def drive(app: App, events: list[Event]) -> Session:
    """Fold a scripted *events* list through a fresh :class:`Session` over *app*.

    Each ``SelectorAction`` event is folded through :meth:`Session.dispatch`
    — so a selector that resolves to a registered tool actually EXECUTES it,
    the same as a live agent driving the session — while every other event
    (``UserInput``, ``KeyPress``, etc.) is folded through :meth:`Session.fold`
    directly. Returns the resulting session so a caller can assert on its
    ``state``, ``events`` trail, ``mirror()``, or ``last_result``.
    """
    session = Session(app)
    for event in events:
        if isinstance(event, SelectorAction):
            session.dispatch(event)
        else:
            session.fold(event)
    return session


def _step_key_toward(order: list[str], current: str, target_index: int) -> str:
    """Return the arrow key that moves *current* one step toward *target_index*.

    ``focus_order`` lists visible panel items first and appends
    ``"input.prompt"`` last, and a fresh session's baseline focus starts
    AT that last entry (see ``agentfront.taui.derive.make_baseline`` /
    ``TAUIState.focused``'s default) — so a human walking the order to reach
    an earlier panel item moves with ``"up"`` (``-1``), only moving
    ``"down"`` (``+1``) when the target sits later in the order than the
    current position. This mirrors exactly how ``_navigate`` in
    ``agentfront.taui.reducer`` interprets each key — it is the same
    step a human pressing arrow keys toward a visible target would take.
    """
    try:
        current_index = order.index(current)
    except ValueError:
        current_index = 0
    return "down" if target_index > current_index else "up"


def assert_agent_human_parity(app: App, selector: str) -> None:
    """Assert the agent's dispatch path and the human's navigation path agree.

    The agent path is a fresh :class:`Session` dispatching a single
    ``SelectorAction(selector=selector)`` — for a selector that is NOT a
    registered tool this is pure navigation (see
    :meth:`Session.dispatch`). The human path is a separate fresh session fed
    arrow-key (``"up"``/``"down"``) presses, walking the focus order one
    step at a time toward ``selector`` until ``state.focused == selector``,
    bounded by ``len(focus_order(state))`` steps (an ``AssertionError`` is
    raised if the selector is never reached that way).

    The two paths fold different events (one ``SelectorAction`` vs. a chain
    of ``KeyPress`` events) so their event trails will differ — what must
    match is the resulting STATE (dataclass equality), not the trail. Raises
    ``AssertionError`` naming both final ``focused`` values on mismatch.

    *selector* must be pure navigation on the agent side too: a selector that
    resolves to a REGISTERED TOOL executes on dispatch and has no
    human-navigation equivalent, so it is rejected up front with a dedicated
    ``AssertionError`` (pick a non-tool panel item, e.g. a host command's
    ``cmd.<name>`` selector).
    """
    if app.get_by_path(tuple(selector.split("."))) is not None:
        raise AssertionError(
            f"selector {selector!r} resolves to a registered tool: dispatching it"
            " EXECUTES the tool on the agent path, which has no human-navigation"
            " equivalent — pass a pure-navigation selector instead (e.g. a host"
            " command's 'cmd.<name>' panel item)"
        )

    agent_session = Session(app)
    agent_state = agent_session.dispatch(SelectorAction(selector=selector))

    human_session = Session(app)
    order = focus_order(human_session.state)
    target_index = order.index(selector) if selector in order else None

    if target_index is not None:
        for _ in range(len(order)):
            if human_session.state.focused == selector:
                break
            key = _step_key_toward(order, human_session.state.focused, target_index)
            human_session.feed_key(key)

    human_state = human_session.state
    if human_state.focused != selector:
        raise AssertionError(
            f"selector {selector!r} not reachable via arrow-key navigation "
            f"(focus order: {order!r})"
        )

    if agent_state != human_state:
        raise AssertionError(
            f"agent/human parity mismatch for selector {selector!r}: "
            f"agent path focused={agent_state.focused!r}, "
            f"human path focused={human_state.focused!r}"
        )


def assert_replay_equivalent(session: Session) -> None:
    """Assert *session*'s own trail replays to its own current state.

    Checks ``replay(session.events[session.replay_base_index:],
    initial=session.initial) == session.state`` — true for both a fresh
    session (``replay_base_index == 0``) and a resumed one (only the events
    folded since resumption are replayed, on top of the state it resumed
    from). Raises ``AssertionError`` with the replayed and actual states on
    mismatch.
    """
    replayed = replay(session.events[session.replay_base_index :], initial=session.initial)
    if replayed != session.state:
        raise AssertionError(
            "replay-equivalence violated: replay(session.events"
            f"[{session.replay_base_index}:], initial=session.initial) != session.state\n"
            f"  replayed: {replayed!r}\n"
            f"  actual:   {session.state!r}"
        )


def __getattr__(name: str) -> Any:
    """PEP 562 lazy module attribute — see the module docstring for why.

    Resolved via plain attribute access on the imported module (not
    ``from agentfront.taui.snapshot import resume``) so that, while the
    sibling task has not landed ``resume`` yet, the failure surfaces as a
    plain ``AttributeError`` naming ``resume`` — the same exception shape
    ``__getattr__`` raises for any other unknown name — rather than an
    ``ImportError`` from the ``from ... import`` form.
    """
    if name == "resume":
        from agentfront.taui import snapshot as _snapshot

        return _snapshot.resume
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
