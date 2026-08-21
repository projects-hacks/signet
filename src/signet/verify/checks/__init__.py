"""One module per signal.

Every check implements the same protocol and produces exactly one Signal. Adding
a signal means adding a file and a registry entry; the pipeline and the verdict
engine stay shut.
"""

from __future__ import annotations

from typing import Protocol

from signet.core.verdict import Signal
from signet.verify.context import VerificationContext


class Check(Protocol):
    name: str

    def run(self, context: VerificationContext) -> Signal: ...
