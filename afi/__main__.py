"""Allow running afi as ``python -m afi``."""

import sys

from afi.cli import main

if __name__ == "__main__":
    sys.exit(main())
