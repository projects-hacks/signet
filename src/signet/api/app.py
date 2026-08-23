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

import uuid
from datetime import date
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from signet.adapters.dns_multi import DohResolver
from signet.adapters.local_store import DEFAULT_PATH, LocalRecordStore
from signet.adapters.nutrient import NutrientClient, NutrientExtractor
from signet.adapters.qr import ImageMarkReader
from signet.adapters.rdap import RdapRegistrationData
from signet.config import Settings, load_settings
from signet.core.verdict import Decision
from signet.errors import SignetError
from signet.verify.pipeline import VerificationPipeline, VerificationRequest
from signet.verify.registry import default_checks

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


def _decision_json(run_id: str, decision: Decision) -> dict[str, Any]:
    return {
        "runId": run_id,
        "verdict": decision.verdict.value,
        "reason": decision.reason,
        "signals": [
            {
                "name": signal.name,
                "outcome": signal.outcome.value,
                "detail": signal.detail,
                "source": signal.source,
                "evidence": dict(signal.evidence),
            }
            for signal in decision.signals
        ],
    }


def build_pipeline(settings: Settings, store_path: Path) -> VerificationPipeline:
    store = LocalRecordStore(store_path)
    extractor = (
        NutrientExtractor(NutrientClient(settings.nutrient.values[0]))
        if settings.nutrient.configured and not settings.fixtures
        else None
    )
    return VerificationPipeline(
        checks=default_checks(
            DohResolver(), store, RdapRegistrationData(), date.today(), extractor
        ),
        store=store,
        mark_reader=ImageMarkReader(),
    )


def create_app(
    settings: Settings | None = None,
    store_path: Path = DEFAULT_PATH,
    static_root: Path | None = Path("web/dist"),
) -> Starlette:
    resolved = settings or load_settings()
    pipeline = build_pipeline(resolved, store_path)

    async def health(request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "fixtures": resolved.fixtures,
                "extraction": resolved.nutrient.configured and not resolved.fixtures,
            }
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

        return JSONResponse(_decision_json(run_id, decision))

    routes: list[Route | Mount] = [
        Route("/api/health", health, methods=["GET"]),
        Route("/api/verify", verify, methods=["POST"]),
    ]
    if static_root is not None and static_root.is_dir():
        routes.append(Mount("/", app=StaticFiles(directory=static_root, html=True), name="web"))

    return Starlette(routes=routes)
