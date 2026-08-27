import { useRef, useState } from "react";
import { verifyDocument } from "./api.js";
import Regions from "./components/Regions.jsx";
import Stamp from "./components/Stamp.jsx";
import Working from "./components/Working.jsx";

const READING = {
  certified: "Signed by the domain this brand signs from, and the page matches what was signed.",
  flagged: "Something about this document contradicts itself.",
  unsigned: "No proof available. Nothing here contradicts the document either.",
};

export default function App() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [brand, setBrand] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const picker = useRef(null);

  function take(next) {
    if (!next) return;
    setFile(next);
    setPreview(URL.createObjectURL(next));
    setResult(null);
    setError(null);
  }

  async function examine(event) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await verifyDocument(file, brand));
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy(false);
    }
  }

  const fidelity = result?.signals.find((signal) => signal.name === "fidelity");
  const signature = result?.signals.find((signal) => signal.name === "signature");
  const issuer = signature?.evidence?.query?.replace(/^_signet\./, "");
  const compared = fidelity?.evidence?.compared ?? [];

  return (
    <div className="record">
      <header className="masthead">
        <h1 className="wordmark">Signet</h1>
        <span className="label">Examination record</span>
      </header>

      <section className="examination">
        <div className="sheet">
          {preview ? (
            <>
              <img src={preview} alt="The document under examination" />
              {result && (
                <Regions compared={compared} threshold={fidelity?.evidence?.threshold ?? 0.8} />
              )}
              {result && <Stamp verdict={result.verdict} issuer={issuer} />}
            </>
          ) : (
            <div className="sheet-empty">
              <span className="label">No document yet</span>
              <p style={{ margin: 0 }}>
                An invoice, a receipt, a statement. Anything that arrived and asks to be paid.
              </p>
            </div>
          )}
        </div>

        <form className="finding" onSubmit={examine}>
          {result ? (
            <>
              <p className="label">The finding</p>
              <p className="finding-reason">{result.reason}</p>
              <p style={{ margin: 0, color: "var(--muted)" }}>{READING[result.verdict]}</p>
            </>
          ) : (
            <>
              <p className="label">Examine a document</p>
              <p className="finding-reason">
                Who really sent this, and does the page still say what they signed?
              </p>
            </>
          )}

          <input
            ref={picker}
            type="file"
            accept="image/*,application/pdf"
            hidden
            onChange={(event) => take(event.target.files?.[0])}
          />
          <button
            type="button"
            className="dropzone"
            data-over={String(over)}
            onClick={() => picker.current?.click()}
            onDragOver={(event) => {
              event.preventDefault();
              setOver(true);
            }}
            onDragLeave={() => setOver(false)}
            onDrop={(event) => {
              event.preventDefault();
              setOver(false);
              take(event.dataTransfer.files?.[0]);
            }}
          >
            <span className="label">{file ? "Document" : "Choose or drop a document"}</span>
            <span className="mono">{file ? file.name : "PNG, JPEG or PDF"}</span>
          </button>

          <label className="brand-field">
            <span className="label">Who does it claim to be from?</span>
            <input
              value={brand}
              onChange={(event) => setBrand(event.target.value)}
              placeholder="Northpost"
              autoComplete="organization"
            />
          </label>

          <button type="submit" className="dropzone" disabled={!file || busy}>
            <span className="label">{busy ? "Examining" : "Examine"}</span>
            <span className="mono">
              {busy ? "reading DNS, comparing the page" : "checks the signature against public DNS"}
            </span>
          </button>

          {error && (
            <p className="mono" style={{ color: "var(--refuse)", margin: 0 }}>
              {error}
            </p>
          )}
        </form>
      </section>

      {result && <Working signals={result.signals} />}

      {result && issuer && (
        <section className="selfcheck">
          <p className="label">Check it yourself</p>
          <p>
            None of the above needs to be taken on trust. The key is a public DNS record, so the
            same answer is available to anyone with a terminal and no account here.
          </p>
          <code className="command">dig +short TXT _signet.{issuer}</code>
        </section>
      )}
    </div>
  );
}
