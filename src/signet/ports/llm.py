"""Text generation, kept away from the verdict.

The model writes the paragraph that explains signals a human already computed. It
never decides anything. Behind a port so the provider is configuration, not a
dependency.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class LlmClient(Protocol):
    def complete(self, prompt: str, max_tokens: int) -> str: ...


class ToolCallingClient(Protocol):
    """One turn of a tool calling conversation.

    Stated in the shape every OpenAI compatible provider already speaks, because
    inventing our own would mean translating twice and the translation is where
    a tool call quietly loses an argument.
    """

    def complete(
        self, messages: Sequence[Mapping[str, Any]], tools: Sequence[Mapping[str, Any]]
    ) -> Mapping[str, Any]: ...
