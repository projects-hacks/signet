"""What the agent can do, and what it cannot do no matter what it is told.

The tools are the safety, not the prompt. This is not a stylistic preference; it
is what the measurement showed. Given a lookalike enrolment and told to hurry,
one capable model skipped the diligence lookup entirely and another ran it, saw
that the brand publishes a different domain, and enrolled the lookalike anyway
while reporting the check as passed. Neither noticed the contradiction it was
holding. ADR 0007 has the transcripts.

So every ordering rule and every refusal below is a precondition in code. An
agent that calls these out of order is told no and carries on, and the answer it
gets back is an ordinary tool result rather than an exception, because a refusal
is information the model should act on rather than a crash.

Three rules, in the order they bite:

  Diligence before drafting. An authorisation nobody checked is a form.
  The signing domain is compared by us, never by the model.
  Publishing is not here at all. It lives on the broker, which the agent
  cannot reach.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Final

from signet.core.lookalike import is_confusable
from signet.core.signing import generate_key
from signet.errors import SignetError
from signet.issue.broker import EnrolmentBroker, Pending
from signet.ports.intelligence import EntityResolver

MAX_DILIGENCE_CHARACTERS: Final = 600


class ToolRefused(SignetError):
    """A precondition said no. The agent is told, and nothing happened."""


@dataclass
class Toolbox:
    """The agent's whole reach.

    State lives here rather than in the conversation, so what the agent believes
    and what is true cannot drift. A model claiming a key was generated does not
    make one exist.
    """

    resolver: EntityResolver
    broker: EnrolmentBroker
    resolved: dict[str, Any] | None = field(default=None, init=False)
    keys: dict[str, tuple[bytes, bytes]] = field(default_factory=dict, init=False)
    pending: Pending | None = field(default=None, init=False)

    def resolve_counterparty(self, brand: str) -> dict[str, Any]:
        """What the open web publishes for this brand."""
        resolution = self.resolver.resolve_brand(brand)
        self.resolved = {
            "brand": brand,
            "published_domain": resolution.canonical_domain,
            "sources": list(resolution.sources),
        }
        return self.resolved

    def generate_signing_key(self, domain: str) -> dict[str, Any]:
        """Generate a keypair. Publishes nothing and commits to nothing."""
        private, public = generate_key()
        self.keys[domain] = (private, public)
        return {"domain": domain, "fingerprint": _fingerprint(public), "published": False}

    def draft_authorisation(
        self, domain: str, brand: str, signer_email: str, signer_name: str = ""
    ) -> dict[str, Any]:
        """Generate the authorisation and send it for a human signature.

        Every precondition in the system is enforced here, because this is the
        last step before a person is asked for their name.
        """
        # Drafting is the expensive step: it generates a document, reads it back
        # through a conversion, and creates an envelope that costs five credits
        # whether or not anyone signs. A model that retries after a clarifying
        # question must not spend all of that again.
        if (
            self.pending is not None
            and self.pending.domain == domain
            and self.pending.brand == brand
        ):
            return self._sent(signer_email)

        if self.resolved is None:
            raise ToolRefused(
                "Nothing has been looked up yet. Call resolve_counterparty for this "
                "brand before drafting an authorisation for it."
            )
        if self.resolved["brand"].strip().casefold() != brand.strip().casefold():
            raise ToolRefused(
                f"The lookup was for {self.resolved['brand']!r} and this authorisation "
                f"is for {brand!r}. Look up the brand being enrolled."
            )

        published = self.resolved["published_domain"]
        if published and published != domain:
            # The exact case both models walked straight past.
            reason = (
                f"reads as {published} without being it"
                if is_confusable(domain, published)
                else f"is not {published}"
            )
            raise ToolRefused(
                f"The open web publishes {published} for {brand}, and {domain} {reason}. "
                "Enrolling this would let a lookalike sign as the brand. Refused. If "
                "the brand really does issue from this domain, a person has to enrol "
                "it by hand."
            )

        if domain not in self.keys:
            raise ToolRefused(f"No key has been generated for {domain} yet.")

        _, public = self.keys[domain]
        self.pending = self.broker.request_release(
            domain=domain,
            brand=brand,
            public_key=public,
            signer_email=signer_email,
            signer_name=signer_name or _name_from(signer_email),
            diligence=self._diligence(),
        )
        return self._sent(signer_email)

    def _sent(self, signer_email: str) -> dict[str, Any]:
        assert self.pending is not None
        return {
            "domain": self.pending.domain,
            "envelope_id": self.pending.envelope_id,
            "authorisation_reference": self.pending.authorisation_hash,
            "sent_to": signer_email,
            "published": False,
            "next": (
                "A person signs. The broker publishes the key only after reading the "
                "signed document back and finding this reference in it. There is "
                "nothing further for you to do."
            ),
        }

    def publish_key_to_dns(self, domain: str) -> dict[str, Any]:
        """Present so that reaching for it is answered rather than unhandled.

        Leaving it out of the catalogue would make an agent that wants to publish
        invent something else. Naming it and refusing it ends the attempt with an
        explanation the model can report back to whoever asked.
        """
        raise ToolRefused(
            f"Publishing the key for {domain} is not something you can do. It is "
            "irreversible: the domain would vouch for every document signed with "
            "that key, to everyone, indefinitely. Only the broker publishes, and "
            "only against a countersigned authorisation."
        )

    def _diligence(self) -> str:
        """What was checked, in words the person signing can read."""
        assert self.resolved is not None
        published = self.resolved["published_domain"]
        sources = self.resolved["sources"]
        if published:
            found = f"Live search reports {self.resolved['brand']} publishing {published}."
        else:
            found = (
                f"Live search returned no published domain for {self.resolved['brand']}, "
                "so the domain below rests on your word alone."
            )
        if sources:
            found += f" Sources consulted: {', '.join(sources[:3])}."
        return found[:MAX_DILIGENCE_CHARACTERS]


def _name_from(signer_email: str) -> str:
    """Address a person when nobody said who they are.

    Better than an empty name on the envelope, and it is visibly a fallback
    rather than a guess at somebody's actual name.
    """
    local = signer_email.split("@", 1)[0]
    words = [part for part in local.replace(".", " ").replace("_", " ").split() if part]
    return " ".join(word.capitalize() for word in words) or "Authorised Signatory"


def _fingerprint(public_key: bytes) -> str:
    import hashlib

    digest = hashlib.sha256(public_key).hexdigest()[:32].upper()
    return ":".join(digest[index : index + 4] for index in range(0, len(digest), 4))


SCHEMAS: Final = [
    {
        "type": "function",
        "function": {
            "name": "resolve_counterparty",
            "description": (
                "Look up a brand on the live web and return the domain it publishes. "
                "Required before an authorisation can be drafted."
            ),
            "parameters": {
                "type": "object",
                "properties": {"brand": {"type": "string"}},
                "required": ["brand"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_signing_key",
            "description": "Generate an Ed25519 keypair for a domain. Publishes nothing.",
            "parameters": {
                "type": "object",
                "properties": {"domain": {"type": "string"}},
                "required": ["domain"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_authorisation",
            "description": (
                "Generate the enrolment authorisation and send it to the domain owner "
                "for signature. This is the last step you can take."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string"},
                    "brand": {"type": "string"},
                    "signer_email": {"type": "string"},
                    "signer_name": {
                        "type": "string",
                        "description": "Optional. Derived from the address when not known.",
                    },
                },
                "required": ["domain", "brand", "signer_email"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "publish_key_to_dns",
            "description": (
                "Publish the signing key as a DNS TXT record. IRREVERSIBLE, and not "
                "available to you. Only the broker publishes, after a person signs."
            ),
            "parameters": {
                "type": "object",
                "properties": {"domain": {"type": "string"}},
                "required": ["domain"],
            },
        },
    },
]


def call(toolbox: Toolbox, name: str, arguments: str) -> str:
    """Run one tool and return what the model should see.

    A refusal comes back as an ordinary result rather than an exception, because
    the model needs to read it, explain it, and stop.
    """
    try:
        parsed = json.loads(arguments or "{}")
    except ValueError:
        return json.dumps({"error": "Arguments were not valid JSON."})
    if not isinstance(parsed, dict):
        return json.dumps({"error": "Arguments must be an object."})

    handler = getattr(toolbox, name, None)
    if handler is None or name.startswith("_"):
        return json.dumps({"error": f"There is no tool called {name}."})
    try:
        return json.dumps(handler(**parsed))
    except ToolRefused as refusal:
        return json.dumps({"refused": str(refusal)})
    except TypeError as wrong:
        return json.dumps({"error": f"Wrong arguments for {name}: {wrong}"})
    except SignetError as failure:
        return json.dumps({"error": str(failure)})
