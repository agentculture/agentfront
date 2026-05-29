"""Allow running agentfront as ``python -m agentfront``."""

import sys

from agentfront.cli import main

if __name__ == "__main__":
    sys.exit(main())
