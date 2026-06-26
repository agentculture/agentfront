"""agentfront — Agent First Interface runtime.

Import :class:`App`, declare your docs + tools once, and derive all three
agent-first surfaces (CLI, MCP, HTTP) from that single source of truth.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _v

from agentfront import _brand
from agentfront.app import App
from agentfront.errors import AgentfrontError

try:
    __version__ = _v(_brand.DIST)
except PackageNotFoundError:  # editable install without metadata
    __version__ = "0.0.0+local"

__all__ = ["AgentfrontError", "App", "__version__"]
