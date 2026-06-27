"""TAUIState — the single source of truth for the TUI cockpit.

A plain dataclass tree that round-trips through JSON. Every node carries a
stable string id so selectors can address it unambiguously. No view-specific
(ANSI/markdown/render) fields exist — only structural state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Header:
    """Top-of-screen header information."""

    title: str = ""
    subtitle: str = ""
    version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"title": self.title, "subtitle": self.subtitle, "version": self.version}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Header:
        return cls(title=d["title"], subtitle=d.get("subtitle", ""), version=d.get("version", ""))


@dataclass(frozen=True)
class PanelItem:
    """A single item inside a panel."""

    id: str
    label: str
    status: str = "available"
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "status": self.status, "tags": list(self.tags)}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PanelItem:
        return cls(
            id=d["id"],
            label=d["label"],
            status=d.get("status", "available"),
            tags=list(d.get("tags", [])),
        )


@dataclass(frozen=True)
class Panel:
    """A group of related items."""

    id: str
    title: str = ""
    visible: bool = True
    content_summary: str = ""
    items: list[PanelItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "visible": self.visible,
            "content_summary": self.content_summary,
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Panel:
        return cls(
            id=d["id"],
            title=d.get("title", ""),
            visible=d.get("visible", True),
            content_summary=d.get("content_summary", ""),
            items=[PanelItem.from_dict(i) for i in d.get("items", [])],
        )


@dataclass(frozen=True)
class Action:
    """A user-action that can be dispatched."""

    selector: str
    input: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"selector": self.selector, "input": self.input, "description": self.description}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Action:
        return cls(
            selector=d["selector"],
            input=d["input"],
            description=d.get("description", ""),
        )


@dataclass(frozen=True)
class Popup:
    """An overlay dialog."""

    id: str
    kind: str
    visible: bool = False
    blocking: bool = False
    opened_by: str = "system"
    reason: str = ""
    message: str = ""
    actions: list[Action] = field(default_factory=list)
    timeout_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "visible": self.visible,
            "blocking": self.blocking,
            "opened_by": self.opened_by,
            "reason": self.reason,
            "message": self.message,
            "actions": [a.to_dict() for a in self.actions],
            "timeout_ms": self.timeout_ms,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Popup:
        return cls(
            id=d["id"],
            kind=d["kind"],
            visible=d.get("visible", False),
            blocking=d.get("blocking", False),
            opened_by=d.get("opened_by", "system"),
            reason=d.get("reason", ""),
            message=d.get("message", ""),
            actions=[Action.from_dict(a) for a in d.get("actions", [])],
            timeout_ms=d.get("timeout_ms"),
        )


@dataclass(frozen=True)
class Zone:
    """A screen region."""

    visible: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"visible": self.visible}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Zone:
        return cls(visible=d.get("visible", True))


@dataclass(frozen=True)
class Status:
    """Status bar information."""

    severity: str = "info"
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"severity": self.severity, "message": self.message}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Status:
        return cls(severity=d.get("severity", "info"), message=d.get("message", ""))


@dataclass(frozen=True)
class WorkItem:
    """A work item being processed."""

    task_id: str = ""
    engine: str = ""
    step_count: int = 0
    running: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "engine": self.engine,
            "step_count": self.step_count,
            "running": self.running,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WorkItem:
        return cls(
            task_id=d.get("task_id", ""),
            engine=d.get("engine", ""),
            step_count=d.get("step_count", 0),
            running=d.get("running", False),
        )


@dataclass(frozen=True)
class Background:
    """Background theme and animation state."""

    theme: str = ""
    animation: str = ""
    frame: int = 0
    semantic: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "theme": self.theme,
            "animation": self.animation,
            "frame": self.frame,
            "semantic": self.semantic,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Background:
        return cls(
            theme=d.get("theme", ""),
            animation=d.get("animation", ""),
            frame=d.get("frame", 0),
            semantic=d.get("semantic", ""),
        )


@dataclass(frozen=True)
class ConversationLine:
    """A conversation line with consecutive-duplicate collapse count."""

    text: str
    count: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "count": self.count}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ConversationLine:
        return cls(text=d["text"], count=d.get("count", 1))

    def render(self) -> str:
        """Render as plain text, or 'text ×N' when count > 1."""
        return self.text if self.count <= 1 else f"{self.text} ×{self.count}"


@dataclass(frozen=True)
class TAUIState:
    """The single source of truth for the TUI cockpit.

    Every field is structural state only — no view-specific (ANSI/markdown/
    render) information. The state tree round-trips through JSON via
    :meth:`to_dict` / :meth:`from_dict`.
    """

    screen: str = "main"
    mode: str = "planning"
    focused: str = "input.prompt"
    header: Header = field(default_factory=lambda: Header(""))
    zones: dict[str, Zone] = field(
        default_factory=lambda: {
            "top.status": Zone(),
            "left.skills": Zone(),
            "main.conversation": Zone(),
            "bottom.input": Zone(),
        }
    )
    panels: list[Panel] = field(default_factory=list)
    popups: list[Popup] = field(default_factory=list)
    status: Status = field(default_factory=Status)
    work_item: WorkItem | None = None
    problems: list[dict] = field(default_factory=list)
    background: Background = field(default_factory=Background)
    conversation: list[ConversationLine] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "screen": self.screen,
            "mode": self.mode,
            "focused": self.focused,
            "header": self.header.to_dict(),
            "zones": {k: v.to_dict() for k, v in self.zones.items()},
            "panels": [p.to_dict() for p in self.panels],
            "popups": [p.to_dict() for p in self.popups],
            "status": self.status.to_dict(),
            "work": self.work_item.to_dict() if self.work_item is not None else None,
            "problems": list(self.problems),
            "background": self.background.to_dict(),
            "conversation": [c.to_dict() for c in self.conversation],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TAUIState:
        work_item = None
        work_raw = d.get("work")
        if work_raw is not None:
            work_item = WorkItem.from_dict(work_raw)
        return cls(
            screen=d.get("screen", "main"),
            mode=d.get("mode", "planning"),
            focused=d.get("focused", "input.prompt"),
            header=Header.from_dict(d["header"]) if "header" in d else Header(""),
            zones={k: Zone.from_dict(v) for k, v in d.get("zones", {}).items()},
            panels=[Panel.from_dict(p) for p in d.get("panels", [])],
            popups=[Popup.from_dict(p) for p in d.get("popups", [])],
            status=Status.from_dict(d["status"]) if "status" in d else Status(),
            work_item=work_item,
            problems=list(d.get("problems", [])),
            background=Background.from_dict(d["background"]) if "background" in d else Background(),
            conversation=[ConversationLine.from_dict(c) for c in d.get("conversation", [])],
        )
