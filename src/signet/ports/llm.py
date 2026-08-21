"""Text generation, kept away from the verdict.

The model writes the paragraph that explains signals a human already computed. It
never decides anything. Behind a port so the provider is configuration, not a
dependency.
"""

from __future__ import annotations

from typing import Protocol


class LlmClient(Protocol):
    def complete(self, prompt: str, max_tokens: int) -> str: ...
