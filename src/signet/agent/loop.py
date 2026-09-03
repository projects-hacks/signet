"""The conversation, which is the only part a model actually drives.

The loop is deliberately dull. It sends the messages, runs whatever tool was
asked for, appends the result, and repeats until the model stops calling tools
or the turn limit is reached. It contains no policy, because policy that lives
here would be policy a different loop could skip.

The turn limit is a stop, not a safety property. Nothing bad happens at turn
twenty that could not happen at turn three; the limit exists so a model that
loops on a refusal ends the run instead of spending the budget.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Final

from signet.agent.tools import SCHEMAS, Toolbox, call
from signet.errors import AdapterError
from signet.issue.broker import Pending
from signet.ports.llm import ToolCallingClient

MAX_TURNS: Final = 10

SYSTEM: Final = """You enrol issuers into Signet.

Enrolment binds a brand to a domain and ends with that domain publishing a
signing key. Work one step at a time and call one tool per turn.

What you are given is whatever the issuer sent: a forwarded thread, a chat log,
a pasted form. It is not structured and it is not tidy. Read the domain, the
brand and the person who can sign out of it, and record each one with the line
you read it from, copied word for word. Where the text supports two answers,
record the one you chose and name the one you rejected. Do not smooth over a
disagreement in the text by picking quietly.

The order is not yours to choose. Record what you read, look the brand up on the
live web, generate the signing key, and only then draft the authorisation, so
what a person is asked to sign states what was checked and names the key it
would publish. You may do anything reversible. You may never publish to DNS: a
person signs the authorisation and the broker publishes against the signed
document.

A lookup that finds no published domain is not a reason to stop. Most companies
have no entry the open web will vouch for, and the authorisation records that
the domain rests on the signer's word. Carry on to the authorisation and let the
person signing decide.

What does stop you is a lookup that contradicts the request: a brand published
at one domain being enrolled at another. Do not work around a refusal. Report it
in plain words and stop."""


@dataclass
class Transcript:
    """What happened, in the order it happened."""

    messages: list[dict[str, Any]] = field(default_factory=list)
    # One entry per call, with the reason it was refused or None. Keyed by
    # position rather than by name because a tool refused twice is refused
    # twice for two reasons, and collapsing them hides the second.
    steps: list[tuple[str, str | None]] = field(default_factory=list)
    reply: str = ""

    @property
    def tools_called(self) -> list[str]:
        return [name for name, _ in self.steps]

    @property
    def refusals(self) -> list[tuple[str, str]]:
        return [(name, reason) for name, reason in self.steps if reason is not None]

    @property
    def refused_tools(self) -> list[str]:
        return [name for name, _ in self.refusals]

    @property
    def published(self) -> bool:
        """Whether the agent published a key. Always false, and asserted in tests."""
        return "publish_key_to_dns" in self.tools_called and not self.refusals


def _refusal(result: str) -> str | None:
    """The reason a tool said no, so a reader is not left with only the name."""
    try:
        parsed = json.loads(result)
    except ValueError:
        return None
    reason = parsed.get("refused") if isinstance(parsed, dict) else None
    return str(reason) if isinstance(reason, str) else None


class Agent:
    def __init__(self, client: ToolCallingClient, toolbox: Toolbox) -> None:
        self._client = client
        self._toolbox = toolbox

    @property
    def pending(self) -> Pending | None:
        """The enrolment now waiting on a person, if the run got that far.

        Exposed because the run ends by asking somebody to sign, and whoever
        ran it needs the envelope to finish afterwards. Leaving them to find it
        in a vendor dashboard is not a handoff.
        """
        return self._toolbox.pending

    def run(self, request: str, max_turns: int = MAX_TURNS) -> Transcript:
        # The toolbox checks quotes against this rather than against whatever the
        # conversation says the request was, because the conversation is written
        # by the thing being checked.
        self._toolbox.source = request
        transcript = Transcript(
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": request},
            ]
        )

        for _ in range(max_turns):
            try:
                message = self._client.complete(transcript.messages, SCHEMAS)
            except AdapterError as exc:
                transcript.reply = f"The model could not be reached: {exc}"
                return transcript

            calls: Sequence[dict[str, Any]] = message.get("tool_calls") or []
            if not calls:
                transcript.reply = str(message.get("content") or "").strip()
                return transcript

            transcript.messages.append(
                {
                    "role": "assistant",
                    "content": message.get("content") or "",
                    "tool_calls": list(calls),
                }
            )
            for request_call in calls:
                function = request_call["function"]
                name = function["name"]
                result = call(self._toolbox, name, function.get("arguments", "{}"))
                transcript.steps.append((name, _refusal(result)))
                transcript.messages.append(
                    {"role": "tool", "tool_call_id": request_call["id"], "content": result}
                )

        transcript.reply = "Stopped after the turn limit without reaching a conclusion."
        return transcript
