"""A thin HTTP surface over the verification pipeline.

Thin is the requirement, not a preference. Every decision this returns is made
by the same pipeline the command line drives, so the browser cannot reach a
verdict the library would not, and a judge running the CLI sees what the screen
showed. Nothing here interprets a signal or decides anything.

The pipeline is built once at startup rather than per request. Building it per
request would open a fresh DNS client and a fresh extractor for every upload,
and the resolver's connection reuse is most of why a verification is fast.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, Final

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from signet.adapters.local_store import DEFAULT_PATH
from signet.adapters.records import record_store
from signet.adapters.samples import SampleError, SampleMinter
from signet.config import Settings, load_settings
from signet.core.shape import well_formed
from signet.core.verdict import Decision, Outcome, Signal, decide
from signet.errors import SignetError
from signet.verify.adjudication import NotAdjudicable, apply_reading
from signet.verify.pipeline import VerificationRequest
from signet.wiring import build_pipeline

# Anything larger is a scan nobody photographed, and reading it into memory to
# find a QR code is how a demo machine falls over in front of an audience.
MAX_UPLOAD_BYTES = 20 * 1024 * 1024

_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}


def _media_type(filename: str) -> str:
    return _MEDIA_TYPES.get(Path(filename).suffix.lower(), "application/octet-stream")


RUN_NAMESPACE: Final = "run"


def _signals_from(stored: Mapping[str, Any]) -> list[Signal]:
    """Rebuild the signals of a stored run.

    Tolerant on the way in because the store is a vendor and an unrecognised
    outcome should read as unknown rather than raise on a page a person is
    trying to resolve.
    """
    raw = stored.get("signals")
    if not isinstance(raw, list):
        return []
    signals: list[Signal] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        try:
            outcome = Outcome(entry.get("outcome"))
        except ValueError:
            outcome = Outcome.UNKNOWN
        evidence = entry.get("evidence")
        signals.append(
            Signal(
                name=str(entry.get("name", "")),
                outcome=outcome,
                detail=str(entry.get("detail", "")),
                source=str(entry.get("source", "")),
                evidence=evidence if isinstance(evidence, dict) else {},
            )
        )
    return signals


def _line(payload: Mapping[str, object]) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"


def _signal_json(signal: Signal) -> dict[str, Any]:
    return {
        "name": signal.name,
        "outcome": signal.outcome.value,
        "detail": signal.detail,
        "source": signal.source,
        "evidence": dict(signal.evidence),
    }


def _decision_json(run_id: str, decision: Decision) -> dict[str, Any]:
    return {
        "runId": run_id,
        "verdict": decision.verdict.value,
        "reason": decision.reason,
        "signals": [_signal_json(signal) for signal in decision.signals],
    }


def _withhold_signed(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip the signed value from any field a person is about to read.

    Somebody reading a page with the expected answer in front of them is being
    led, and a reading produced that way is not evidence of anything. The full
    values stay in the stored run, which is what adjudication re-decides from;
    only the response a reader sees goes out without them. Once the field is
    settled it is no longer uncertain, and the next response carries the value.
    """
    return {
        **payload,
        "signals": [_withhold_from(signal) for signal in payload.get("signals", [])],
    }


def _withhold_from(signal: dict[str, Any]) -> dict[str, Any]:
    evidence = signal.get("evidence")
    if not isinstance(evidence, dict):
        return signal
    uncertain = set(evidence.get("uncertain", ()))
    if signal.get("name") != "fidelity" or not uncertain:
        return signal
    compared = [
        {**row, "signed": None} if row.get("field") in uncertain else row
        for row in evidence.get("compared", ())
        if isinstance(row, dict)
    ]
    return {**signal, "evidence": {**evidence, "compared": compared}}


def create_app(
    settings: Settings | None = None,
    store_path: Path = DEFAULT_PATH,
    static_root: Path | None = Path("web/dist"),
) -> Starlette:
    resolved = settings or load_settings()
    pipeline = build_pipeline(resolved, store_path)
    store = record_store(resolved, store_path)
    minter = SampleMinter(keys_env=resolved.sample_keys)

    async def health(request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "fixtures": resolved.fixtures,
                "extraction": resolved.nutrient.configured and not resolved.fixtures,
                "samples": minter.available,
            }
        )

    async def sample(request: Request) -> Response:
        """A fresh signed demo document, minted for whoever asks.

        Signed per request rather than served from a file, because the ledger
        is global and a static sample is spent by its first visitor. The page
        never changes; the signature and its timestamp do.
        """
        try:
            minted = minter.mint(request.path_params["kind"])
        except SampleError as exc:
            return JSONResponse({"error": str(exc)}, status_code=404)
        return Response(
            minted.content,
            media_type="image/png",
            headers={
                "Content-Disposition": f'attachment; filename="{minted.filename}"',
                # Every response is a different document. Nothing may cache it.
                "Cache-Control": "no-store",
            },
        )

    async def verify(request: Request) -> JSONResponse:
        form = await request.form()
        upload = form.get("file")
        if not hasattr(upload, "read") or not hasattr(upload, "filename"):
            return JSONResponse({"error": "Attach a document as the file field."}, status_code=400)

        content = await upload.read()  # type: ignore[union-attr]
        if not content:
            return JSONResponse({"error": "That file is empty."}, status_code=400)
        if len(content) > MAX_UPLOAD_BYTES:
            return JSONResponse({"error": "That file is too large to verify."}, status_code=413)

        brand = form.get("brand")
        run_id = uuid.uuid4().hex[:12]
        try:
            decision = pipeline.run(
                VerificationRequest(
                    run_id=run_id,
                    content=content,
                    media_type=_media_type(str(upload.filename)),  # type: ignore[union-attr]
                    submitted_by="web",
                    claimed_brand=str(brand) if isinstance(brand, str) and brand.strip() else None,
                )
            )
        except SignetError as exc:
            # A vendor being down is not a verdict. Saying so beats inventing one.
            return JSONResponse({"error": str(exc)}, status_code=502)

        payload = _decision_json(run_id, decision)
        store.cache_put(RUN_NAMESPACE, run_id, payload)
        return JSONResponse(_withhold_signed(payload))

    # A page served from static hosting is a different origin from the process
    # that verifies, so the browser asks first. Named origins only, and only the
    # verify endpoint is reachable this way.
    middleware = (
        [
            Middleware(
                CORSMiddleware,
                allow_origins=list(resolved.allowed_origins),
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["*"],
            )
        ]
        if resolved.allowed_origins
        else []
    )

    async def adjudicate(request: Request) -> JSONResponse:
        """A person answers what the extractor could not read.

        The run is loaded from the store rather than from the request, so a
        caller cannot post their own signals and have them re-decided. The only
        thing they supply is one reading of one field.
        """
        try:
            body = await request.json()
        except ValueError:
            return JSONResponse({"error": "Send a JSON body."}, status_code=400)
        if not isinstance(body, dict):
            return JSONResponse({"error": "Send a JSON object."}, status_code=400)

        run_id = str(body.get("runId", "")).strip()
        field = str(body.get("field", "")).strip()
        reading = str(body.get("reading", "")).strip()
        by = str(body.get("by", "")).strip() or "web"
        if not run_id or not field or not reading:
            return JSONResponse(
                {"error": "A run, a field and what the page says are all required."},
                status_code=400,
            )

        stored = store.cache_get(RUN_NAMESPACE, run_id)
        if stored is None:
            return JSONResponse(
                {"error": "That examination is no longer on file."}, status_code=404
            )
        # The whole argument of the shape check is that a value which cannot be
        # what it claims to be was not read cleanly. That argument does not
        # stop applying because a person typed it: a slip of the finger is not
        # a reading either, and comparing it as one manufactures a mismatch.
        if not well_formed(field, reading):
            return JSONResponse(
                {"error": f"{reading!r} cannot be a value for {field}. Check for a typo."},
                status_code=422,
            )

        try:
            amended = apply_reading(_signals_from(stored), field, reading, by)
        except NotAdjudicable as refusal:
            return JSONResponse({"error": str(refusal)}, status_code=409)

        decision = decide(amended)
        payload = _decision_json(run_id, decision)
        store.cache_put(RUN_NAMESPACE, run_id, payload)
        # A person overriding a machine reading is exactly the event an audit
        # trail exists for, so it is recorded before the answer is returned.
        store.append_audit(
            run_id,
            "adjudicated",
            {"field": field, "reading": reading, "by": by, "verdict": decision.verdict.value},
        )
        return JSONResponse(_withhold_signed(payload))

    async def examine(request: Request) -> Response:
        """The same verification, reported as it happens.

        One JSON object per line. The first names every check this run will ask,
        so a reader sees the shape of the answer immediately; each signal follows
        as it lands; the verdict is last. Newline delimited rather than server
        sent events because the document arrives by POST and EventSource cannot
        send one.
        """
        form = await request.form()
        upload = form.get("file")
        if not hasattr(upload, "read") or not hasattr(upload, "filename"):
            return JSONResponse({"error": "Attach a document as the file field."}, status_code=400)
        content = await upload.read()  # type: ignore[union-attr]
        if not content:
            return JSONResponse({"error": "That file is empty."}, status_code=400)
        if len(content) > MAX_UPLOAD_BYTES:
            return JSONResponse({"error": "That file is too large to verify."}, status_code=413)

        brand = form.get("brand")
        run_id = uuid.uuid4().hex[:12]
        verification = VerificationRequest(
            run_id=run_id,
            content=content,
            media_type=_media_type(str(upload.filename)),  # type: ignore[union-attr]
            submitted_by="web",
            claimed_brand=str(brand) if isinstance(brand, str) and brand.strip() else None,
        )

        def lines() -> Iterator[bytes]:
            yield _line({"event": "started", "runId": run_id, "checks": pipeline.check_names})
            try:
                for step in pipeline.stream(verification):
                    if isinstance(step, Decision):
                        payload = _decision_json(run_id, step)
                        # Kept so a person can answer a doubtful reading later
                        # without the document being uploaded again.
                        store.cache_put(RUN_NAMESPACE, run_id, payload)
                        yield _line({"event": "decided", **_withhold_signed(payload)})
                    else:
                        yield _line({"event": "signal", **_withhold_from(_signal_json(step))})
            except SignetError as exc:
                # A vendor being down is not a verdict. The stream has already
                # started, so this arrives as a final line rather than a status.
                yield _line({"event": "failed", "error": str(exc)})

        return StreamingResponse(lines(), media_type="application/x-ndjson")

    routes: list[Route | Mount] = [
        Route("/api/health", health, methods=["GET"]),
        Route("/api/sample/{kind}", sample, methods=["GET"]),
        Route("/api/verify", verify, methods=["POST"]),
        Route("/api/examine", examine, methods=["POST"]),
        Route("/api/adjudicate", adjudicate, methods=["POST"]),
    ]
    # Mounted last and only when built, so the API keeps answering during a
    # frontend rebuild rather than the whole app failing to start.
    if static_root is not None and static_root.is_dir():
        routes.append(Mount("/", app=StaticFiles(directory=static_root, html=True), name="web"))

    return Starlette(routes=routes, middleware=middleware)
