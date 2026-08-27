"""Which renderer the environment is configured for.

Choosing an adapter is configuration, not domain logic, so it lives here rather
than in the caller. Everything above this line sees a DocumentRenderer.
"""

from __future__ import annotations

from signet.adapters.doctavian import DoctavianRenderer
from signet.adapters.doctavian_auth import RefreshingToken
from signet.config import Settings
from signet.ports.documents import DocumentRenderer


def document_renderer(settings: Settings) -> DocumentRenderer:
    api_key, base_url = settings.doctavian.require()
    return DoctavianRenderer(
        api_key=api_key,
        token_provider=RefreshingToken(api_key, base_url),
        templates=settings.doctavian_templates,
        base_url=base_url,
    )
