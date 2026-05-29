"""agentfront — Agent First Interface scaffolder."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _v

from agentfront import _brand

try:
    __version__ = _v(_brand.DIST)
except PackageNotFoundError:  # editable install without metadata
    __version__ = "0.0.0+local"

__all__ = ["__version__"]
