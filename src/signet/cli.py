"""Signet from the command line.

Four verbs, matching what actually happens: make a key, publish it, issue a
document, verify one. Nothing here holds logic of its own. It wires adapters to
the pipeline and prints the result, so anything it can do the library can do.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

from signet.adapters.dns_multi import DohResolver
from signet.adapters.local_store import DEFAULT_PATH
from signet.adapters.namecom import NameComClient, NameComDns
from signet.adapters.nutrient import NutrientClient, NutrientExtractor
from signet.adapters.page import page_with_mark
from signet.adapters.qr import ImageMarkReader, render_mark
from signet.adapters.rdap import RdapRegistrationData
from signet.adapters.records import record_store
from signet.adapters.renderers import document_renderer
from signet.config import load_settings
from signet.constants import DNS_LABEL
from signet.core.mark import encode_mark, format_locator
from signet.core.payload import canonicalize
from signet.core.signing import Ed25519Signer, encode_public_key, generate_key
from signet.core.verdict import Outcome, Verdict
from signet.errors import SignetError
from signet.issue.publish import KeyPublisher
from signet.verify.pipeline import VerificationPipeline, VerificationRequest
from signet.verify.registry import default_checks

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

    username, token, base_url = load_settings().namecom.require()
    publisher = KeyPublisher(NameComDns(NameComClient(username, token, base_url)), DohResolver())
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


def verify(args: argparse.Namespace) -> int:
    """Run one document through the pipeline and print every signal."""
    path = Path(args.file)
    if not path.is_file():
        print(f"no such file: {path}", file=sys.stderr)
        return 1

    settings = load_settings()
    store = record_store(settings, Path(args.store))
    # Without an extractor the pipeline simply runs one check fewer, so an
    # unconfigured Nutrient degrades the verdict's depth rather than breaking it.
    extractor = (
        NutrientExtractor(NutrientClient(settings.nutrient.values[0]))
        if settings.nutrient.configured and not settings.fixtures
        else None
    )
    pipeline = VerificationPipeline(
        checks=default_checks(
            DohResolver(), store, RdapRegistrationData(), date.today(), extractor
        ),
        store=store,
        mark_reader=ImageMarkReader(),
    )
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
    parser.add_argument("--store", default=str(DEFAULT_PATH), help="path to the local record store")
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("keygen", help="generate a signing key and show the DNS record")
    generate.add_argument("--domain", required=True)
    generate.add_argument("--brand", required=True)
    generate.set_defaults(handler=keygen)

    send = sub.add_parser("publish", help="write the key to DNS and confirm it resolves")
    send.add_argument("--domain", required=True)
    send.add_argument("--attempts", type=int, default=10)
    send.add_argument("--delay", type=float, default=6.0)
    send.set_defaults(handler=publish)

    make = sub.add_parser("issue", help="sign fields and draw the mark")
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

    check = sub.add_parser("verify", help="verify a document")
    check.add_argument("file")
    check.add_argument("--brand", default=None, help="the brand the document claims to be from")
    check.add_argument("--by", default="cli")
    check.set_defaults(handler=verify)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result: int = args.handler(args)
    except SignetError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return result


if __name__ == "__main__":
    sys.exit(main())
