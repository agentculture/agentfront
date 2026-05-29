"""Entry point for ``python -m {{module}}``."""

from __future__ import annotations

import sys

from {{module}}.cli import main

if __name__ == "__main__":
    sys.exit(main())
