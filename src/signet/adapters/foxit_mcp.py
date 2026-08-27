"""Foxit's own MCP server, run as a subprocess and called over stdio.

Their challenge is explicit: register the server and the agent gets the tools
for the reversible work. So this launches their published server rather than
reimplementing its endpoints, which means the tool list, the argument shapes and
the polling behaviour are theirs and stay theirs when they change.

Two things follow from that choice and are worth stating.

The server is a separate process holding a session, so it is opened once and
closed once rather than per call. Everything here runs inside a context manager
and the process is torn down even when a call raises.

Their tools return text, because that is what MCP carries. A document id comes
back inside a JSON string rather than as a typed value, so the parsing at the
bottom of this file is the price of the boundary and is kept in one place.

What the server deliberately does not carry is signing. Foxit left it out of the
catalogue, and we agree with the shape of that decision while disagreeing about
where the line sits: signing a document is reversible, an envelope can be
voided, and the act that cannot be undone here is publishing a key to DNS. So
eSign is called directly, from the broker, and DNS is reachable from neither.
"""

from __future__ import annotations

import asyncio
import base64
import json
import sys
import tempfile
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

from signet.errors import AdapterError

# Three upstream defects sit between us and their server, and none of them is in
# the server itself, which works correctly once it is running. Their tool
# definitions and their polling are what we wanted and what we use.
#
#   1. pyproject declares the console script as foxit_pdf_api_mcp.main:main
#      while the package they ship is foxit_pdf_api_mcp_server, so the installed
#      executable raises ModuleNotFoundError on its first line.
#   2. main.py has no __main__ guard, so running it with -m imports the module
#      and exits without starting anything.
#   3. main() calls asyncio.run(mcp.run()), and FastMCP 3's run() is
#      synchronous, so it serves one request and then dies on
#      "a coroutine was expected, got None".
#
# So their server object is started directly. All three stop mattering the day
# any of those lines is fixed, and none of them changes what the server does.
SERVER_START: Final = "from foxit_pdf_api_mcp_server.server import mcp; mcp.run()"
SERVICES_SEGMENT: Final = "/pdf-services"


@dataclass(frozen=True, slots=True)
class ToolResult:
    """What a tool returned, before anyone decides what it means."""

    text: str

    def json(self) -> dict[str, Any]:
        try:
            parsed = json.loads(self.text)
        except ValueError as exc:
            raise AdapterError(f"Foxit MCP returned a non-JSON result: {self.text[:200]}") from exc
        if not isinstance(parsed, dict):
            raise AdapterError(f"unexpected Foxit MCP result shape: {self.text[:200]}")
        return parsed


class FoxitMcp:
    """A session against Foxit's MCP server.

    Use it as an async context manager. The server is their process, holding
    their credentials from the environment they document, and it lives exactly
    as long as the block.
    """

    def __init__(
        self,
        host: str,
        client_id: str,
        client_secret: str,
        interpreter: str | None = None,
    ) -> None:
        # Their server has its own dependency set, so it usually runs under its
        # own interpreter rather than ours.
        self._interpreter = interpreter
        # Their server treats the host as the whole base and appends /api
        # directly, while our own calls carry the product segment in the path.
        # Both are right for their own caller, so the segment is added here
        # rather than duplicated through configuration.
        base = host.rstrip("/")
        if not base.endswith(SERVICES_SEGMENT):
            base = f"{base}{SERVICES_SEGMENT}"
        self._env = {
            "FOXIT_CLOUD_API_HOST": base,
            "FOXIT_CLOUD_API_CLIENT_ID": client_id,
            "FOXIT_CLOUD_API_CLIENT_SECRET": client_secret,
        }
        self._session: ClientSession | None = None

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[FoxitMcp]:
        interpreter = self._interpreter or sys.executable
        parameters = StdioServerParameters(
            command=interpreter, args=["-c", SERVER_START], env=self._env
        )
        try:
            async with (
                stdio_client(parameters) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                self._session = session
                try:
                    yield self
                finally:
                    self._session = None
        except AdapterError:
            raise
        except Exception as exc:
            raise AdapterError(f"could not run the Foxit MCP server: {_because(exc)}") from exc

    async def tool_names(self) -> tuple[str, ...]:
        """Whatever their server offers, asked rather than assumed."""
        listed = await self._require().list_tools()
        return tuple(tool.name for tool in listed.tools)

    async def call(self, name: str, **arguments: Any) -> ToolResult:
        result = await self._require().call_tool(name, arguments)
        # MCP content is a union of part types and only the text ones carry
        # anything we can read, so the rest are dropped rather than coerced.
        text = "\n".join(part.text for part in result.content if isinstance(part, TextContent))
        if result.is_error:
            raise AdapterError(f"Foxit MCP tool {name} failed: {text[:200]}")
        return ToolResult(text)

    async def upload(self, filename: str, content: bytes) -> str:
        """Hand them the bytes.

        Their upload takes base64 rather than a path, which is what we want: the
        document exists in memory and writing it to disk to hand over a filename
        would be putting an authorisation on the filesystem for no reason.
        """
        return _identifier(
            await self.call(
                "upload_document",
                fileContent=base64.b64encode(content).decode("ascii"),
                fileName=filename,
            ),
            "documentId",
        )

    async def text_of(self, document_id: str) -> str:
        """Convert to text and hand back what the document actually says.

        Their conversion is asynchronous and their server does the polling, which
        is the main reason this goes through the server rather than around it.
        """
        started = await self.call("pdf_to_text", documentId=document_id)
        result_id = _identifier(started, "resultDocumentId", "documentId", "taskId")

        # Their download writes to a path rather than returning bytes, so it
        # gets a temporary one that is removed whatever happens next. The file
        # holds a converted authorisation and has no business outliving the call.
        with tempfile.TemporaryDirectory() as directory:
            landing = Path(directory) / "converted.txt"
            await self.call("download_document", documentId=result_id, outputPath=str(landing))
            try:
                return landing.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                raise AdapterError(f"Foxit MCP downloaded nothing to read: {exc}") from exc

    def _require(self) -> ClientSession:
        if self._session is None:
            raise AdapterError("The Foxit MCP session is not open. Use connect().")
        return self._session


class McpTextReader:
    """Implements the broker's TextReader over their MCP server.

    Synchronous, because the broker is, and reading a document back is the only
    thing it needs from this. A session is opened for the one call and closed
    again: their server holds credentials and a subprocess, and neither should
    outlive the question being asked.
    """

    def __init__(self, mcp: FoxitMcp) -> None:
        self._mcp = mcp

    def text_of_document(self, document: bytes) -> str:
        async def read() -> str:
            async with self._mcp.connect() as session:
                document_id = await session.upload("authorisation.pdf", document)
                return await session.text_of(document_id)

        return asyncio.run(read())


def _because(error: BaseException) -> str:
    """The innermost reason, which a task group otherwise hides.

    An ExceptionGroup reports only that something inside it failed, so the
    message a caller sees says nothing about what actually went wrong.
    """
    while isinstance(error, BaseExceptionGroup) and error.exceptions:
        error = error.exceptions[0]
    return f"{type(error).__name__}: {error}"


def _identifier(result: ToolResult, *names: str) -> str:
    """Dig an id out of their envelope, wherever they put it.

    Their tools wrap a payload in a success envelope and different tools nest it
    differently, so the search is over the shapes actually observed rather than
    a single assumed path.
    """
    body = result.json()
    for candidate in (body, body.get("data"), body.get("result")):
        if not isinstance(candidate, Mapping):
            continue
        for name in names:
            value = candidate.get(name)
            if isinstance(value, str) and value:
                return value
    raise AdapterError(f"no {names[0]} in the Foxit MCP result: {result.text[:200]}")
