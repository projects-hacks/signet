/* Where the verifier lives, and how its answers arrive.

   The frontend can be served from the same process as the API, or from static
   hosting that runs no server side code at all. Static hosting also answers an
   unknown path with the homepage rather than a 404, so a misconfigured base URL
   comes back as HTML with a 200. Parsing that as JSON gives a syntax error and
   an unreadable message, which is why the content type is checked first. */

const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

/* Checks take unequal time: a DNS read answers in milliseconds, reading the page
   is an upload to an extraction service. The stream reports each one as it
   lands, so `onEvent` is called with {event: "started" | "signal" | "decided" |
   "failed"} and the caller renders progress that is real rather than animated. */
export async function checkDocument(file, brand, onEvent, signal) {
  const body = new FormData();
  body.append("file", file);
  if (brand.trim()) body.append("brand", brand.trim());

  let response;
  try {
    response = await fetch(`${BASE}/api/examine`, { method: "POST", body, signal });
  } catch (cause) {
    if (cause.name === "AbortError") throw cause;
    throw new Error("The verifier could not be reached from here.");
  }

  const type = response.headers.get("content-type") ?? "";
  if (!response.ok && type.includes("application/json")) {
    throw new Error((await response.json()).error ?? "The check could not run.");
  }
  if (!type.includes("ndjson")) {
    throw new Error("This page is not connected to a verifier. It is serving static files only.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let decision = null;

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    // A chunk boundary lands anywhere, so the tail stays buffered until its
    // newline arrives rather than being parsed as a truncated object.
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.trim()) continue;
      const message = JSON.parse(line);
      if (message.event === "failed") throw new Error(message.error);
      if (message.event === "decided") decision = message;
      onEvent(message);
    }
  }

  if (!decision) throw new Error("The check ended before reaching a verdict.");
  return decision;
}

/* A person answering what the extractor could not read. The run is loaded
   server side from its id, so the only thing sent is one reading of one
   field. */
export async function adjudicate(runId, field, reading) {
  const response = await fetch(`${BASE}/api/adjudicate`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ runId, field, reading }),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error ?? "That reading could not be applied.");
  return payload;
}

/* Whether this deployment can hand out demo documents at all. */
export async function verifierHealth() {
  try {
    const response = await fetch(`${BASE}/api/health`);
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}

/* A demo document, signed at the moment of asking. Each request is a new
   document to the ledger, so the genuine one certifies for every visitor
   rather than only the first. */
export async function sampleDocument(kind) {
  const response = await fetch(`${BASE}/api/sample/${kind}`);
  if (!response.ok) throw new Error("The sample could not be fetched.");
  const blob = await response.blob();
  return new File([blob], `sample-${kind}.png`, { type: "image/png" });
}
