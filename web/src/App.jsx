import { useEffect, useRef, useState } from "react";
import { examineDocument } from "./api.js";
import Copy from "./components/Copy.jsx";
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
  const [live, setLive] = useState(null);
  const [error, setError] = useState(null);
  const [over, setOver] = useState(false);
  /* Every examination this session, newest first. Revisiting one costs nothing
     and never re-runs it. Re-examining is deliberately a separate act: the same
     document submitted twice is genuinely a different question, because the
     second time it has been seen before. */
  const [history, setHistory] = useState([]);
  const picker = useRef(null);
  const running = useRef(null);

  useEffect(() => () => running.current?.abort(), []);
  useEffect(() => {
    if (!preview) return undefined;
    return () => URL.revokeObjectURL(preview);
  }, [preview]);

  function take(next) {
    if (!next) return;
    running.current?.abort();
    setFile(next);
    setPreview(URL.createObjectURL(next));
    setResult(null);
    setLive(null);
    setError(null);
  }

  async function examine(event) {
    event.preventDefault();
    if (!file || live) return;
    setError(null);
    setResult(null);
    const controller = new AbortController();
    running.current = controller;

    try {
      const decision = await examineDocument(
        file,
        brand,
        (message) => {
          // The frame arrives first and fills in. The verdict is never
          // anticipated: a stamp that appears before the answer would be the
          // one optimistic thing this product must not do.
          if (message.event === "started") setLive({ checks: message.checks, signals: [] });
          if (message.event === "signal") {
            setLive((current) =>
              current ? { ...current, signals: [...current.signals, message] } : current,
            );
          }
        },
        controller.signal,
      );
      setResult(decision);
      setHistory((past) => [
        { id: decision.runId, name: file.name, preview, brand, decision },
        ...past.filter((entry) => entry.id !== decision.runId),
      ]);
    } catch (cause) {
      if (cause.name !== "AbortError") setError(cause.message);
    } finally {
      running.current = null;
      setLive(null);
    }
  }

  function revisit(entry) {
    running.current?.abort();
    setFile(null);
    setPreview(entry.preview);
    setBrand(entry.brand);
    setResult(entry.decision);
    setLive(null);
    setError(null);
  }

  const shown = result;
  const fidelity = shown?.signals.find((signal) => signal.name === "fidelity");
  const signature = shown?.signals.find((signal) => signal.name === "signature");
  const issuer = signature?.evidence?.query?.replace(/^_signet\./, "");
  const compared = fidelity?.evidence?.compared ?? [];
  const answered = live?.signals.map((signal) => signal.name) ?? [];
  const waiting = live?.checks.filter((name) => !answered.includes(name)) ?? [];

  return (
    <div className="record">
      <header className="masthead">
        <a className="wordmark" href="/">
          Signet
        </a>
        <span className="label">Examination record</span>
      </header>

      <section className="examination">
        <div className="sheet" data-busy={String(Boolean(live))}>
          {preview ? (
            <>
              <img src={preview} alt="The document under examination" />
              {shown && (
                <Regions compared={compared} threshold={fidelity?.evidence?.threshold ?? 0.8} />
              )}
              {shown && <Stamp verdict={shown.verdict} issuer={issuer} />}
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
          {shown ? (
            <>
              <p className="label">The finding</p>
              <p className="finding-reason">{shown.reason}</p>
              <p style={{ margin: 0, color: "var(--muted)" }}>{READING[shown.verdict]}</p>
            </>
          ) : live ? (
            <>
              <p className="label">Examining</p>
              <p className="finding-reason">
                {live.signals.length} of {live.checks.length} checks answered.
              </p>
              <p className="skeleton skeleton-line" />
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

          <button type="submit" className="dropzone" disabled={!file || Boolean(live)}>
            <span className="label">{live ? "Examining" : "Examine"}</span>
            <span className="mono">
              {live
                ? (live.signals.at(-1)?.name ?? "reading the mark").replace("_", " ")
                : "checks the signature against public DNS"}
            </span>
          </button>

          {error && (
            <p className="mono failure" role="alert">
              {error}
            </p>
          )}
        </form>
      </section>

      {(shown || live) && (
        <Working signals={shown?.signals ?? live?.signals ?? []} pending={waiting} />
      )}

      {history.length > 1 && (
        <section className="history">
          <p className="label">Examined this session</p>
          <ul>
            {history.map((entry) => (
              <li key={entry.id}>
                <button
                  type="button"
                  onClick={() => revisit(entry)}
                  data-current={String(entry.id === shown?.runId)}
                >
                  <span className="verdict-dot" data-verdict={entry.decision.verdict} />
                  <span className="mono">{entry.name}</span>
                  <span className="label">{entry.decision.verdict}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {shown && issuer && (
        <section className="selfcheck">
          <p className="label">Check it yourself</p>
          <p>
            None of the above needs to be taken on trust. The key is a public DNS record, so the
            same answer is available to anyone with a terminal and no account here.
          </p>
          <div className="command-row">
            <code className="command">dig +short TXT _signet.{issuer}</code>
            <Copy text={`dig +short TXT _signet.${issuer}`} label="Copy command" />
          </div>
        </section>
      )}
    </div>
  );
}
