"""Nutrient, against the Data Extraction shapes confirmed against the live service."""

from __future__ import annotations

import json
from io import BytesIO
from typing import Any

import httpx
import pytest
from PIL import Image

from signet.adapters.nutrient import NutrientClient, NutrientExtractor
from signet.errors import AdapterError


def cited(value: str, confidence: float, page: int = 0) -> dict[str, Any]:
    return {
        "value": value,
        "meta": {
            "bbox": {"x": 300.0, "y": 247.0, "width": 240.0, "height": 33.0},
            "confidence": confidence,
            "pageIndex": page,
            "pageNumber": page + 1,
        },
    }


def responder(fields: dict[str, dict[str, Any]], absent: tuple[str, ...] = ()) -> Any:
    """Reproduce their envelope, including nulled metadata for absent fields."""
    data = {name: item["value"] for name, item in fields.items()}
    metadata = {name: item["meta"] for name, item in fields.items()}
    for name in absent:
        metadata[name] = {"bbox": None, "confidence": None, "pageIndex": None}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"status": 200, "output": {"data": data, "metadata": metadata}}
        )

    return handler


def client(handler: Any) -> NutrientClient:
    return NutrientClient("key", client=httpx.Client(transport=httpx.MockTransport(handler)))


def extract(handler: Any) -> Any:
    return NutrientExtractor(client(handler)).extract(b"%PDF", "application/pdf")


def test_a_cited_field_carries_its_value_and_confidence() -> None:
    extraction = extract(responder({"iban": cited("GB29 NWBK 6016 1331 9268 19", 0.95)}))
    field = extraction.by_name()["iban"]
    assert field.value == "GB29 NWBK 6016 1331 9268 19"
    assert field.confidence == pytest.approx(0.95)
    assert field.page == 0


def test_a_box_is_a_fraction_of_the_page() -> None:
    """Nutrient reports pixels. A reviewer's screen is a different size."""
    page = BytesIO()
    Image.new("RGB", (600, 800), "white").save(page, format="PNG")
    extraction = NutrientExtractor(client(responder({"iban": cited("GB29", 0.95)}))).extract(
        page.getvalue(), "image/png"
    )

    box = extraction.by_name()["iban"].box
    assert box is not None
    # The fixture cites x 300, y 247 on a 600 by 800 page.
    assert box.left == pytest.approx(0.5)
    assert box.top == pytest.approx(0.30875)


def test_a_box_we_cannot_place_is_dropped_rather_than_guessed() -> None:
    """Placing a box needs the page it was measured on. These bytes are not one.

    A missing box costs a reviewer a highlight. A wrong one points confidently
    at the wrong part of the document, which is worse than not pointing.
    """
    field = extract(responder({"iban": cited("GB29", 0.95)})).by_name()["iban"]
    assert field.box is None


def test_a_box_beyond_the_first_page_is_dropped() -> None:
    """Only the first page is rendered, so only its boxes have anything to sit on."""
    page = BytesIO()
    Image.new("RGB", (600, 800), "white").save(page, format="PNG")
    extraction = NutrientExtractor(
        client(responder({"iban": cited("GB29", 0.95, page=2)}))
    ).extract(page.getvalue(), "image/png")

    field = extraction.by_name()["iban"]
    assert field.page == 2
    assert field.box is None


def test_a_box_running_off_the_page_is_dropped() -> None:
    """A box outside the page means the units were not the ones we measured in."""
    page = BytesIO()
    Image.new("RGB", (100, 800), "white").save(page, format="PNG")
    extraction = NutrientExtractor(client(responder({"iban": cited("GB29", 0.95)}))).extract(
        page.getvalue(), "image/png"
    )

    assert extraction.by_name()["iban"].box is None


def test_confidence_is_not_rescaled() -> None:
    """The Processor API reports 0 to 100. This one already reports a fraction."""
    field = extract(responder({"amt": cited("1240.00", 0.95)})).by_name()["amt"]
    assert field.confidence == pytest.approx(0.95)


def test_a_field_absent_from_the_page_is_not_returned() -> None:
    """Their metadata carries nulled entries for misses, so data decides."""
    extraction = extract(responder({"id": cited("INV-1", 0.95)}, absent=("iban", "bic")))
    assert set(extraction.by_name()) == {"id"}


def test_a_value_without_a_citation_is_given_no_confidence() -> None:
    """No provenance means a human looks at it, not that we trust it."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"output": {"data": {"id": "INV-1"}, "metadata": {}}})

    field = extract(handler).by_name()["id"]
    assert field.confidence == 0.0
    assert field.box is None


def test_the_schema_names_our_fields_and_asks_for_strings() -> None:
    """A number turns 1240.00 into 1240 and breaks comparison on presentation."""
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode("utf-8", "replace")
        marker = 'name="instructions"\r\n\r\n'
        start = body.index(marker) + len(marker)
        seen.update(json.loads(body[start : body.index("\r\n--", start)]))
        return httpx.Response(200, json={"output": {"data": {}, "metadata": {}}})

    extract(handler)
    properties = seen["schema"]["properties"]
    assert set(properties) == {"id", "amt", "cur", "iban", "bic"}
    assert {spec["type"] for spec in properties.values()} == {"string"}
    assert seen["options"]["includeCitations"] is True


def test_an_unentitled_key_is_reported_as_entitlement_not_a_bad_key() -> None:
    """403 after a clean 401 baseline means the key is real but the product is not ours."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": {"details": "Forbidden"}})

    with pytest.raises(AdapterError, match="not entitled"):
        extract(handler)


def test_an_unknown_key_is_reported_as_a_bad_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"details": "Unauthorized"}})

    with pytest.raises(AdapterError, match="did not recognise"):
        extract(handler)


def test_a_non_json_body_is_an_adapter_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>gateway</html>")

    with pytest.raises(AdapterError, match="non-JSON"):
        extract(handler)


def test_a_pdf_box_is_placed_in_the_pixels_nutrient_measured_it_in() -> None:
    """Nutrient rasterises a PDF before reading it and reports those pixels.

    The page is 612 by 792 points, which at their render density is 1700 by
    2200 pixels, so the cited x of 300 sits a little under a fifth across. Read
    as points it would land off the page entirely.
    """
    page = BytesIO()
    Image.new("RGB", (1224, 1584), "white").save(page, format="PDF", resolution=144)
    extraction = NutrientExtractor(client(responder({"iban": cited("GB29", 0.95)}))).extract(
        page.getvalue(), "application/pdf"
    )

    box = extraction.by_name()["iban"].box
    assert box is not None
    assert box.left == pytest.approx(300.0 / 1700.0, abs=0.002)
    assert box.top == pytest.approx(247.0 / 2200.0, abs=0.002)
