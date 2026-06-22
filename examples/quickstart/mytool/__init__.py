"""mytool — a tiny third-party package built on agentfront."""

from agentfront import App

app = App(name="mytool", version="0.1.0", description="A minimal example package")

app.add_doc(
    slug="quickstart",
    title="Quickstart",
    text="# Quickstart\n\nRun `mytool learn` to see what this package offers.",
)

app.add_doc(
    slug="reference",
    title="Reference",
    text="# Reference\n\nSee the tools below for available operations.",
)


@app.tool
def add(x: int, y: int) -> int:
    """Add two integers."""
    return x + y


@app.tool
def greet(name: str) -> str:
    """Greet someone by name."""
    return f"Hello, {name}!"
