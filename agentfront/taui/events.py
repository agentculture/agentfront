"""TAUI events — discriminated-union dataclasses and JSONL helpers.

Each event is a frozen dataclass with a ``type`` discriminator, ``to_dict()``,
and ``from_dict()``.  The module exposes ``event_from_dict`` for dispatch,
plus ``dumps_events`` / ``loads_events`` for JSONL serialisation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, ClassVar

# ---------------------------------------------------------------------------
# Event dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UserInput:
    """Text typed by the user."""

    type: ClassVar[str] = "user_input"
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "text": self.text}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> UserInput:
        return cls(text=d["text"])


@dataclass(frozen=True)
class KeyPress:
    """A single key press (e.g. 'enter', 'tab', 'esc', 'up', 'down')."""

    type: ClassVar[str] = "key"
    key: str

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "key": self.key}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> KeyPress:
        return cls(key=d["key"])


@dataclass(frozen=True)
class SelectorAction:
    """The agent's selector-dispatch event."""

    type: ClassVar[str] = "selector_action"
    selector: str
    args: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "selector": self.selector, "args": dict(self.args)}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SelectorAction:
        return cls(selector=d["selector"], args=dict(d.get("args", {})))


@dataclass(frozen=True)
class Tick:
    """A periodic tick."""

    type: ClassVar[str] = "tick"
    delta: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "delta": self.delta}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Tick:
        return cls(delta=d.get("delta", 1))


@dataclass(frozen=True)
class Dismiss:
    """Dismiss a target (e.g. a popup)."""

    type: ClassVar[str] = "dismiss"
    target: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "target": self.target}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Dismiss:
        return cls(target=d.get("target", ""))


@dataclass(frozen=True)
class SkillSuggested:
    """The system recommends a stronger or more specific skill."""

    type: ClassVar[str] = "skill_suggested"
    skill: str = ""
    reason: str = ""
    semantic: str = "stronger_agent_recommended"
    theme: str = "skill_suggested"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "skill": self.skill,
            "reason": self.reason,
            "semantic": self.semantic,
            "theme": self.theme,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SkillSuggested:
        return cls(
            skill=d.get("skill", ""),
            reason=d.get("reason", ""),
            semantic=d.get("semantic", "stronger_agent_recommended"),
            theme=d.get("theme", "skill_suggested"),
        )


@dataclass(frozen=True)
class WorkStep:
    """A step appended to the conversation; may open an error popup on failure."""

    type: ClassVar[str] = "work_step"
    label: str = ""
    ok: bool = True
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "label": self.label,
            "ok": self.ok,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WorkStep:
        return cls(
            label=d.get("label", ""),
            ok=d.get("ok", True),
            error=d.get("error", ""),
        )


# ---------------------------------------------------------------------------
# Registry & dispatch
# ---------------------------------------------------------------------------

Event = UserInput | KeyPress | SelectorAction | Tick | Dismiss | SkillSuggested | WorkStep

_REGISTRY: dict[str, type[Event]] = {
    "user_input": UserInput,
    "key": KeyPress,
    "selector_action": SelectorAction,
    "tick": Tick,
    "dismiss": Dismiss,
    "skill_suggested": SkillSuggested,
    "work_step": WorkStep,
}


def event_from_dict(data: dict[str, Any]) -> Event:
    """Dispatch on ``data["type"]`` to reconstruct the correct event."""
    if not isinstance(data, dict):
        raise ValueError("event_from_dict expects a dict, not " + type(data).__name__)
    type_ = data.get("type")
    if type_ is None:
        raise ValueError("event_from_dict: missing required 'type' field")
    cls = _REGISTRY.get(type_)
    if cls is None:
        raise ValueError(
            f"event_from_dict: unknown event type {type_!r}; expected one of {sorted(_REGISTRY)}"
        )
    try:
        return cls.from_dict(data)
    except KeyError as exc:
        raise ValueError(
            f"event_from_dict: missing required field {exc.args[0]!r} for event type {type_!r}"
        ) from exc


# ---------------------------------------------------------------------------
# JSONL helpers
# ---------------------------------------------------------------------------


def dumps_events(events: list[Event]) -> str:
    """Serialize a list of events to JSONL (newline-terminated)."""
    if not events:
        return ""
    return "\n".join(json.dumps(ev.to_dict()) for ev in events) + "\n"


def loads_events(text: str) -> list[Event]:
    """Parse JSONL text into a list of events, skipping blank lines."""
    result: list[Event] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        result.append(event_from_dict(json.loads(line)))
    return result
