"""Single source of truth for brand-identifying strings.

The project was renamed from ``teken`` to ``agentfront`` (it was ``afi`` before
that). Every user-facing reference to the program name, distribution, or
dot-directory should read from here so a future rename is a one-line change.
``LEGACY_*`` values keep the previous ``teken`` surface working during the
migration; the older ``afi`` surface has been retired.
"""

PROG = "agentfront"  # primary CLI command + argparse prog
LEGACY_PROG = "teken"  # deprecated alias command
DIST = "agentfront"  # canonical PyPI distribution (importlib.metadata key)
LEGACY_DIST = "teken"  # wrapper distribution; self-doctor still recognises it
DOTDIR = ".agentfront"  # primary dot-directory for cited references
LEGACY_DOTDIR = ".teken"  # read-fallback dot-directory (existing trees)
REPO_URL = "https://github.com/agentculture/agentfront"
ISSUES_URL = f"{REPO_URL}/issues"

__all__ = [
    "PROG",
    "LEGACY_PROG",
    "DIST",
    "LEGACY_DIST",
    "DOTDIR",
    "LEGACY_DOTDIR",
    "REPO_URL",
    "ISSUES_URL",
]
