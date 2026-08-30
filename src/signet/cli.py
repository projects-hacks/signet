"""Signet from the command line.

Six verbs, matching what actually happens: make a key, publish it, issue a
document, verify one, enrol an issuer from whatever they sent, and release a
key against a signed authorisation. Nothing here holds logic of its own. It
wires adapters to the pipeline and prints the result, so anything it can do the
library can do.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from signet.adapters.dns_multi import DohResolver
from signet.adapters.local_store import DEFAULT_PATH
from signet.adapters.namecom import NameComClient, NameComDns
from signet.adapters.page import page_with_mark
from signet.adapters.qr import render_mark
from signet.adapters.records import record_store
from signet.adapters.renderers import document_renderer
from signet.agent.loop import MAX_TURNS
from signet.config import load_env_file, load_settings
from signet.constants import DNS_LABEL
from signet.core.mark import encode_mark, format_locator
from signet.core.payload import canonicalize
from signet.core.signing import Ed25519Signer, encode_public_key, generate_key
from signet.core.verdict import Outcome, Verdict
from signet.errors import SignetError
from signet.issue.broker import Pending, ReleaseRefused, authorisation_hash
from signet.issue.publish import KeyPublisher
from signet.verify.pipeline import VerificationRequest
from signet.wiring import build_agent, build_broker, build_pipeline

KEY_DIR = Path(".signet/keys")

_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}

_SYMBOL = {Outcome.PASS: "pass", Outcome.FAIL: "FAIL", Outcome.UNKNOWN: "  ? "}
_HEADLINE = {
    Verdict.CERTIFIED: "CERTIFIED",
    Verdict.UNSIGNED: "UNSIGNED",
    Verdict.FLAGGED: "FLAGGED",
}


def _media_type(path: Path) -> str:
    return _MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")


def _key_path(domain: str) -> Path:
    return KEY_DIR / f"{domain}.key"


def keygen(args: argparse.Namespace) -> int:
    """Generate a signing key and print the record that has to reach DNS."""
    private, public = generate_key()
    path = _key_path(args.domain)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(private)
    path.chmod(0o600)

    record_store(load_settings(), Path(args.store)).enrol(args.domain, args.brand, public)

    print(f"private key  {path}  (mode 600, gitignored)")
    print(f"enrolled     {args.domain} as {args.brand}\n")
    print("Publish this TXT record, then verification works for anyone:\n")
    print(f"  host   {DNS_LABEL}")
    print("  type   TXT")
    print(f"  value  {encode_public_key(public)}")
    print("  ttl    300\n")
    print(f"Check it with:  dig +short TXT {DNS_LABEL}.{args.domain}")
    return 0


def publish(args: argparse.Namespace) -> int:
    """Write the key to DNS, then wait for the public internet to agree."""
    store = record_store(load_settings(), Path(args.store))
    issuer = store.issuer(args.domain)
    if issuer is None:
        print(
            f"{args.domain} is not enrolled. Run: signet keygen --domain {args.domain} "
            "--brand '<brand>'",
            file=sys.stderr,
        )
        return 1

    settings = load_settings()
    username, token, base_url = settings.namecom.require()
    publisher = KeyPublisher(
        NameComDns(NameComClient(username, token, base_url)), DohResolver(settings.resolvers)
    )
    value = publisher.publish(args.domain, issuer.public_key)
    print(f"wrote     TXT {DNS_LABEL}.{args.domain}")

    for attempt in range(1, args.attempts + 1):
        result = publisher.confirm(args.domain, value)
        if result.visible:
            agreed = "agreed" if result.resolvers_agreed else "DISAGREED"
            signed = "validated" if result.dnssec_validated else "unsigned zone"
            print(f"visible   {result.fqdn}")
            print(f"resolvers {agreed}")
            print(f"dnssec    {signed} (advisory)")
            print(f"\nAnyone can now check it:  dig +short TXT {result.fqdn}")
            return 0
        print(f"  not visible yet, retrying ({attempt}/{args.attempts})")
        if attempt < args.attempts:
            time.sleep(args.delay)

    print("the record was written but has not propagated yet", file=sys.stderr)
    return 1


def issue(args: argparse.Namespace) -> int:
    """Sign a set of fields and draw the mark that carries them."""
    path = _key_path(args.domain)
    if not path.is_file():
        print(
            f"no key for {args.domain}. Run: signet keygen --domain {args.domain}", file=sys.stderr
        )
        return 1

    fields = dict(pair.split("=", 1) for pair in args.field)
    fields.setdefault("iss", args.domain)
    fields.setdefault("cls", args.document_class)
    fields.setdefault("id", args.id or f"R-{uuid.uuid4().hex[:8].upper()}")
    fields.setdefault("ts", datetime.now(UTC).replace(microsecond=0).isoformat())

    payload = canonicalize(fields)
    mark = encode_mark(payload, Ed25519Signer(path.read_bytes()).sign(payload))
    locator = format_locator(fields["iss"], fields["id"])

    out = Path(args.out)
    settings = load_settings()
    record = json.loads(Path(args.record).read_text(encoding="utf-8")) if args.record else None

    if record is None:
        # No record, so there is no document to carry the mark and the mark is
        # the artifact. Useful for a quick check, never what a reader receives.
        out.write_bytes(render_mark(mark))
    else:
        document = document_renderer(settings).render(fields["cls"], record, mark, locator)
        out.write_bytes(page_with_mark(document, mark))

    print(f"mark      {len(mark)} bytes")
    print(f"locator   {locator}")
    print(f"written   {out}")
    return 0


def enrol_issuer(args: argparse.Namespace) -> int:
    """Run the enrolment agent, and show every step it took."""
    # Nobody has the request as a sentence. They have the thread it arrived in,
    # so the thread is what the command takes.
    if args.request == "-":
        request = sys.stdin.read()
    elif args.request.startswith("@"):
        request = Path(args.request[1:]).read_text(encoding="utf-8")
    else:
        request = args.request
    if not request.strip():
        print("  nothing to read")
        return 1

    agent = build_agent(load_settings(), Path(args.store))
    transcript = agent.run(request, max_turns=args.turns)

    print()
    for name, reason in transcript.steps:
        print(f"  [{'refused' if reason else 'ok':>7}]  {name}")
        if reason:
            # Without the reason a refusal reads as a failure, and the agent's
            # own summary of what happened is not evidence of what happened.
            print(f"             {reason}")
    print(f"\n  {transcript.reply}\n")
    # A refusal is the system working, so it is not an error. An enrolment that
    # never reached a signature is, because nothing is waiting on a person.
    return 0 if transcript.tools_called else 1


def release(args: argparse.Namespace) -> int:
    """Publish the key, if and only if the signed document says so.

    Separate from the agent on purpose. This is the command that touches DNS,
    and it reads its authority from the executed document rather than from
    whoever ran it.
    """
    settings = load_settings()
    key_path = _key_path(args.domain)
    if not key_path.is_file():
        print(f"no key for {args.domain}", file=sys.stderr)
        return 1

    public = Ed25519Signer(key_path.read_bytes()).public_key
    pending = Pending(
        domain=args.domain,
        brand=args.brand,
        public_key=public,
        envelope_id=args.envelope,
        authorisation_hash=authorisation_hash(args.domain, args.brand, public),
    )
    try:
        released = build_broker(settings, Path(args.store)).release(pending)
    except ReleaseRefused as refusal:
        print(f"\n  refused   {refusal}\n")
        return 2

    print(f"\n  published {released.domain}")
    print(f"  record    {released.record}\n")
    return 0


def verify(args: argparse.Namespace) -> int:
    """Run one document through the pipeline and print every signal."""
    path = Path(args.file)
    if not path.is_file():
        print(f"no such file: {path}", file=sys.stderr)
        return 1

    pipeline = build_pipeline(load_settings(), Path(args.store))
    decision = pipeline.run(
        VerificationRequest(
            run_id=uuid.uuid4().hex[:12],
            content=path.read_bytes(),
            media_type=_media_type(path),
            submitted_by=args.by,
            claimed_brand=args.brand,
        )
    )

    print()
    for signal in decision.signals:
        print(f"  [{_SYMBOL[signal.outcome]}]  {signal.name:12} {signal.detail}")
    print(f"\n  {_HEADLINE[decision.verdict]}")
    print(f"  {decision.reason}\n")
    return 0 if decision.verdict is not Verdict.FLAGGED else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="signet", description=__doc__)
    # On the root and on every subcommand, because every other flag comes after
    # the verb and a flag that only parses before it reads as a bug.
    parser.add_argument("--store", default=str(DEFAULT_PATH), help="path to the local record store")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--store", default=str(DEFAULT_PATH), help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser(
        "keygen", parents=[common], help="generate a signing key and show the DNS record"
    )
    generate.add_argument("--domain", required=True)
    generate.add_argument("--brand", required=True)
    generate.set_defaults(handler=keygen)

    send = sub.add_parser(
        "publish", parents=[common], help="write the key to DNS and confirm it resolves"
    )
    send.add_argument("--domain", required=True)
    send.add_argument("--attempts", type=int, default=10)
    send.add_argument("--delay", type=float, default=6.0)
    send.set_defaults(handler=publish)

    make = sub.add_parser("issue", parents=[common], help="sign fields and draw the mark")
    make.add_argument("--domain", required=True)
    make.add_argument("--class", dest="document_class", default="receipt")
    make.add_argument("--id", default="")
    make.add_argument("--field", action="append", default=[], metavar="KEY=VALUE")
    make.add_argument("--out", default="mark.png")
    make.add_argument(
        "--record",
        default="",
        help="JSON of the document a reader receives, rendered through Doctavian",
    )
    make.set_defaults(handler=issue)

    enrol = sub.add_parser(
        "enrol", parents=[common], help="enrol an issuer from whatever they sent"
    )
    enrol.add_argument(
        "request",
        help="the request itself, @path to read a file, or - to read standard input",
    )
    enrol.add_argument("--turns", type=int, default=MAX_TURNS)
    enrol.set_defaults(handler=enrol_issuer)

    let_go = sub.add_parser(
        "release", parents=[common], help="publish a key against a signed authorisation"
    )
    let_go.add_argument("--domain", required=True)
    let_go.add_argument("--brand", required=True)
    let_go.add_argument("--envelope", required=True)
    let_go.set_defaults(handler=release)

    check = sub.add_parser("verify", parents=[common], help="verify a document")
    check.add_argument("file")
    check.add_argument("--brand", default=None, help="the brand the document claims to be from")
    check.add_argument("--by", default="cli")
    check.set_defaults(handler=verify)
    return parser


def main() -> int:
    # Before anything reads settings. Sourcing the file by hand before every
    # command is a step people forget, and the error it produces blames the
    # configuration rather than the missing step.
    load_env_file()
    args = build_parser().parse_args()
    try:
        result: int = args.handler(args)
    except SignetError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return result


if __name__ == "__main__":
    sys.exit(main())
