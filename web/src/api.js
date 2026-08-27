/* Where the verifier lives.

   The frontend can be served from the same process as the API, or from static
   hosting that runs no server side code at all. Static hosting also answers an
   unknown path with the homepage rather than a 404, so a misconfigured base URL
   comes back as HTML with a 200. Parsing that as JSON gives a syntax error and
   an unreadable message, which is why the content type is checked before the
   body is read. */

const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

export async function verifyDocument(file, brand) {
  const body = new FormData();
  body.append("file", file);
  if (brand.trim()) body.append("brand", brand.trim());

  let response;
  try {
    response = await fetch(`${BASE}/api/verify`, { method: "POST", body });
  } catch {
    throw new Error("The verifier could not be reached from here.");
  }

  if (!response.headers.get("content-type")?.includes("application/json")) {
    throw new Error(
      "This page is not connected to a verifier. It is serving static files only.",
    );
  }

  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error ?? "The examination could not run.");
  return payload;
}
