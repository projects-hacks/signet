"""Doctavian document generation.

Templates carry the branching, so one template handles every shape of a document
class and the payload we sign is produced from a verified record rather than
typed by anyone. That is why generation sits on the issuing path at all.

Four things about their model shape this adapter.

Generation is not one call. Data is uploaded as a file, generation returns a URN
rather than bytes, and the document is fetched separately. So a render is three
requests, not one.

A Data Source and a Document Solution are account level setup, not per document.
provision() creates them once; render() never touches them.

Auth is two headers. The bearer is a personal access token taken from the portal
Authorization tab, and x-api-key is a key from the API Keys tab, scoped to an API
version. The token arrives through a provider rather than as a string so a
future rotating credential drops in without touching this file.

Every upload and download also has to name the storage container it is talking to
through X-Storage-Type, and generation hands back "{guid}:{filename}" while the
download endpoint keys on the guid alone.

Async generation needs a third auth header, x-client-authorization, which the portal
generates rather than the caller constructing it. We generate one document at a
time, so the synchronous endpoint is the right one and that header never
appears.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Final

import httpx

from signet.errors import AdapterError

# Their published spec names api.doctavian.com as the only server, and a key
# issued for one environment is refused by another with ApiKeyInvalid. The
# hackathon account lives on the demo environment, which appears in no spec.
BASE_URL: Final = "https://demo.api.doctavian.com/v1"
_TIMEOUT_SECONDS: Final = 60.0

_DATA_CONTAINER: Final = "document-data"
_TEMPLATE_CONTAINER: Final = "document-template"
# Their download endpoint names three containers and does not say which one holds a
# generated document, so this is the one value here taken from inference rather than
# the spec. Confirm it against a live generate and download before the demo.
_GENERATED_CONTAINER: Final = "document-data"

TokenProvider = Callable[[], str]


@dataclass(frozen=True, slots=True)
class Provisioning:
    """The account level objects a render depends on, created once."""

    data_source_guid: str
    document_solution_guid: str


def _unwrap(response: httpx.Response) -> dict[str, Any]:
    """Pull the payload out of Doctavian's result envelope."""
    try:
        body = response.json()
    except ValueError as exc:
        raise AdapterError(f"Doctavian returned a non-JSON body: {response.text[:200]}") from exc
    result = body.get("result")
    if not isinstance(result, dict) or "data" not in result:
        raise AdapterError(f"unexpected Doctavian response shape: {str(body)[:200]}")
    data = result["data"]
    if not isinstance(data, dict):
        raise AdapterError(f"unexpected Doctavian data shape: {str(data)[:200]}")
    return data


def _first_uploaded_id(data: Mapping[str, Any]) -> str:
    files = data.get("files")
    if not isinstance(files, list) or not files or not isinstance(files[0], dict):
        raise AdapterError("Doctavian upload returned no file id")
    identifier = files[0].get("id")
    if not isinstance(identifier, str):
        raise AdapterError("Doctavian upload returned no file id")
    return identifier


class DoctavianRenderer:
    """Renders a document class from structured fields.

    The mark and locator are passed as ordinary data fields, so the template
    decides where they print and nothing about the signature is vendor specific.
    """

    def __init__(
        self,
        api_key: str,
        token_provider: TokenProvider,
        template_urns: Mapping[str, tuple[str, str]],
        base_url: str = BASE_URL,
        client: httpx.Client | None = None,
        locale: str = "en",
        timezone: str = "UTC",
    ) -> None:
        self._api_key = api_key
        self._token = token_provider
        self._templates = template_urns
        self._base_url = base_url.rstrip("/")
        self._locale = locale
        self._timezone = timezone
        self._client = client or httpx.Client(timeout=_TIMEOUT_SECONDS)

    def render(
        self, document_class: str, fields: Mapping[str, str], mark: str, locator: str
    ) -> bytes:
        template = self._templates.get(document_class)
        if template is None:
            raise AdapterError(
                f"no Doctavian template configured for document class {document_class!r}"
            )
        template_name, template_urn = template

        payload = {**dict(fields), "signet_mark": mark, "signet_locator": locator}
        data_urn = self._upload_data(document_class, payload)
        document_urn = self._generate(document_class, template_name, template_urn, data_urn)
        return self._download(document_urn)

    def provision(self, name: str) -> Provisioning:
        """Create the Data Source and Document Solution. Run once per account."""
        source = _unwrap(
            self._post_json(
                "/documents/datasource/create",
                {"name": f"{name} data", "description": name, "loadMethod": "Storage"},
            )
        )
        data_guid = source.get("dataSourceGuid")
        if not isinstance(data_guid, str):
            raise AdapterError("Doctavian did not return a data source guid")

        solution = _unwrap(
            self._post_json(
                "/documents/solution/create",
                {"name": name, "description": name, "dataGuid": data_guid},
            )
        )
        nested = solution.get("documentSolution")
        solution_guid = nested.get("documentSolutionGuid") if isinstance(nested, dict) else None
        if not isinstance(solution_guid, str):
            raise AdapterError("Doctavian did not return a document solution guid")
        return Provisioning(data_source_guid=data_guid, document_solution_guid=solution_guid)

    def upload_template(self, path: str, content: bytes) -> str:
        """Upload a template file and return the urn to configure against a class."""
        return _first_uploaded_id(
            _unwrap(
                self._post_file("/documents/template/upload", path, content, _TEMPLATE_CONTAINER)
            )
        )

    def ping(self) -> bool:
        """Connectivity check against the endpoint their quickstart uses."""
        response = self._request("GET", "/documents/document/list")
        return response.is_success

    def _upload_data(self, document_class: str, payload: Mapping[str, str]) -> str:
        body = json.dumps(payload, indent=2).encode("utf-8")
        return _first_uploaded_id(
            _unwrap(
                self._post_file(
                    "/documents/data/upload",
                    f"{document_class}.json",
                    body,
                    _DATA_CONTAINER,
                )
            )
        )

    def _generate(
        self, document_class: str, template_name: str, template_urn: str, data_urn: str
    ) -> str:
        data = _unwrap(
            self._post_json(
                "/documents/document/generate",
                {
                    "template": {
                        "name": template_name,
                        "urn": template_urn,
                        "fileFormat": template_name.rsplit(".", 1)[-1],
                        "loadMethod": "Storage",
                    },
                    "data": {"loadMethod": "Storage", "urn": data_urn},
                    "document": {
                        "name": document_class,
                        "fileFormat": "pdf",
                        "deliveryMethod": "Storage",
                        "path": "root",
                        "locale": self._locale,
                        "timezone": self._timezone,
                    },
                },
            )
        )
        document = data.get("document")
        urn = document.get("urn") if isinstance(document, dict) else None
        if not isinstance(urn, str):
            raise AdapterError("Doctavian generation returned no document urn")
        return urn

    def _download(self, document_urn: str) -> bytes:
        # Generation returns "{guid}:{filename}" but download keys on the guid alone,
        # and the file itself comes back rather than a result envelope.
        document_id = document_urn.split(":", 1)[0]
        return self._request(
            "GET",
            f"/documents/document/{document_id}/download",
            headers={"X-Storage-Type": _GENERATED_CONTAINER},
        ).content

    def _post_json(self, path: str, body: Mapping[str, Any]) -> httpx.Response:
        return self._request("POST", path, json=body)

    def _post_file(
        self, path: str, filename: str, content: bytes, container: str
    ) -> httpx.Response:
        return self._request(
            "POST",
            path,
            files={"file": (filename, content)},
            headers={"X-Storage-Type": container},
        )

    def _request(
        self, method: str, path: str, headers: Mapping[str, str] | None = None, **kwargs: Any
    ) -> httpx.Response:
        try:
            response = self._client.request(
                method,
                f"{self._base_url}{path}",
                headers={**self._headers(), **(headers or {})},
                **kwargs,
            )
        except httpx.HTTPError as exc:
            raise AdapterError(f"Doctavian {method} {path} failed: {exc}") from exc
        if response.status_code == 401:
            raise AdapterError(
                "Doctavian rejected the credentials. ApiKeyInvalid means the gateway does "
                "not recognise the x-api-key, which it reports identically for a key that "
                "is merely the wrong area and for one that was never provisioned; omitting "
                "the header instead gives ApiKeyNotFound. Any other 401 is the bearer token."
            )
        if not response.is_success:
            raise AdapterError(
                f"Doctavian {method} {path} returned {response.status_code}: {response.text[:200]}"
            )
        return response

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token()}", "x-api-key": self._api_key}
