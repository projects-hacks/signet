"""The sample minter, which exists so a static sample cannot be spent."""

from __future__ import annotations

import base64
import json
import time
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from signet.adapters.qr import ImageMarkReader
from signet.adapters.samples import SampleError, SampleMinter
from signet.core.mark import decode_mark
from signet.core.signing import Ed25519Verifier, generate_key

DOMAIN = "sample.test"


@pytest.fixture()
def root(tmp_path: Path) -> tuple[Path, bytes]:
    private, _ = generate_key()
    page = BytesIO()
    Image.new("RGB", (1200, 1500), "white").save(page, format="PNG")
    (tmp_path / "page.png").write_bytes(page.getvalue())
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "genuine": {
                    "page": "page.png",
                    "issuer": DOMAIN,
                    "fields": {"cls": "invoice", "id": "INV-1", "amt": "10.00", "cur": "USD"},
                }
            }
        ),
        encoding="utf-8",
    )
    return tmp_path, private


def minter(root: tuple[Path, bytes]) -> SampleMinter:
    path, private = root
    encoded = base64.b64encode(private).decode("ascii")
    return SampleMinter(root=path, keys_env=f"{DOMAIN}={encoded}")


def test_each_minting_is_a_document_the_ledger_has_not_seen(root: tuple[Path, bytes]) -> None:
    """The whole point: a global ledger makes a static sample one-shot."""
    minting = minter(root)
    first = decode_mark(
        ImageMarkReader().read_marks(minting.mint("genuine").content, "image/png")[0]
    )
    time.sleep(1.1)
    second = decode_mark(
        ImageMarkReader().read_marks(minting.mint("genuine").content, "image/png")[0]
    )

    assert first.payload_bytes != second.payload_bytes
    assert first.payload.fields["id"] == second.payload.fields["id"]
    assert first.payload.fields["ts"] != second.payload.fields["ts"]


def test_the_minted_signature_verifies_against_the_declared_issuer(
    root: tuple[Path, bytes],
) -> None:
    _, private = root
    minting = minter(root)
    reader = ImageMarkReader()
    mark = decode_mark(reader.read_marks(minting.mint("genuine").content, "image/png")[0])

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    public = (
        Ed25519PrivateKey.from_private_bytes(private)
        .public_key()
        .public_bytes(Encoding.Raw, PublicFormat.Raw)
    )
    assert Ed25519Verifier().verify(mark.payload_bytes, mark.signature, public)
    assert mark.payload.fields["iss"] == DOMAIN


def test_an_unknown_kind_is_an_answer_not_a_crash(root: tuple[Path, bytes]) -> None:
    with pytest.raises(SampleError, match="no sample called"):
        minter(root).mint("imaginary")


def test_a_missing_key_reports_the_domain(root: tuple[Path, bytes]) -> None:
    path, _ = root
    minting = SampleMinter(root=path, keys_env="")
    if minting.available:
        pytest.skip("a local key store is present for the test domain")
    with pytest.raises(SampleError, match=DOMAIN):
        minting.mint("genuine")


def test_malformed_keys_are_refused_with_the_format(root: tuple[Path, bytes]) -> None:
    path, _ = root
    with pytest.raises(SampleError, match="domain=base64key"):
        SampleMinter(root=path, keys_env="not-a-pair")


def test_no_manifest_means_unavailable_not_broken(tmp_path: Path) -> None:
    assert not SampleMinter(root=tmp_path, keys_env="").available
