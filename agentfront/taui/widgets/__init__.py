"""TAUI widgets — pure functions from TAUIState to a rendered ``str``.

Each widget module exposes a single render function that accepts a
:class:`~agentfront.taui.state.TAUIState` (or a relevant slice) and returns a
``str``.  Widgets are pure (same state -> same output), deterministic, and
stdlib-only — zero third-party imports — so a consumer can compose them into an
interactive cockpit without taking on any rendering dependency.
"""
