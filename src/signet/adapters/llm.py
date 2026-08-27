"""An OpenAI compatible chat provider.

The provider is configuration. NVIDIA's endpoint is what the demo runs on, and
the same code reaches any host speaking the same shape, which is most of them.
Model choice is measured rather than assumed: ADR 0007 records the runs.

Nothing here decides anything. The model orchestrates and the tools refuse, so
a provider outage degrades enrolment to a person doing it by hand rather than to
a wrong enrolment.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final

import httpx

from signet.adapters import http
from signet.errors import AdapterError

_TIMEOUT_SECONDS: Final = 120.0
# Enrolment is a sequence of decisions, not a piece of writing. Sampling buys
# nothing here and costs reproducibility.
_TEMPERATURE: Final = 0.0
_MAX_TOKENS: Final = 1200


class ChatClient:
    """Implements ToolCallingClient."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = client or http.client(
            _TIMEOUT_SECONDS, headers={"Authorization": f"Bearer {api_key}"}
        )

    def complete(
        self, messages: Sequence[Mapping[str, Any]], tools: Sequence[Mapping[str, Any]]
    ) -> Mapping[str, Any]:
        response = self._client.post(
            f"{self._base_url}/chat/completions",
            json={
                "model": self._model,
                "messages": list(messages),
                "tools": list(tools),
                "tool_choice": "auto",
                "temperature": _TEMPERATURE,
                "max_tokens": _MAX_TOKENS,
            },
        )
        if response.status_code == 401:
            raise AdapterError("The model provider rejected the key.")
        if not response.is_success:
            raise AdapterError(
                f"The model provider returned {response.status_code}: {response.text[:200]}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise AdapterError("The model provider returned a non-JSON body.") from exc

        choices = body.get("choices") if isinstance(body, dict) else None
        if not isinstance(choices, list) or not choices:
            raise AdapterError(f"unexpected completion shape: {str(body)[:200]}")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise AdapterError("the completion carried no message")
        return message
