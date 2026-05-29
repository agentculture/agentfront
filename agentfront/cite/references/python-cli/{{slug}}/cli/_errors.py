"""AfiError and exit-code policy (stable-contract — copy verbatim).

Every failure inside {{project_name}} raises :class:`AfiError`. The CLI entry
point catches it and exits with :attr:`AfiError.code`. Guarantees:

* no Python traceback leaks to stderr;
* every error has shape ``{code, message, remediation}``;
* the exit-code policy is centralised.
"""

from __future__ import annotations

from dataclasses import dataclass

# Exit-code policy (documented in ``{{project_name}} learn`` output).
# 0  = success
# 1  = user-input error (bad flag, bad path, missing arg)
# 2  = environment / setup error
# 3+ = reserved
EXIT_SUCCESS = 0
EXIT_USER_ERROR = 1
EXIT_ENV_ERROR = 2


@dataclass
class AfiError(Exception):
    """Structured error with a remediation hint for agents."""

    code: int
    message: str
    remediation: str = ""

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "remediation": self.remediation,
        }
