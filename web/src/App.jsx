import { useEffect, useRef, useState } from "react";
import { adjudicate, checkDocument, sampleDocument, verifierHealth } from "./api.js";
import { checkLabel, uncertainFields } from "./labels.js";
import Adjudicate from "./components/Adjudicate.jsx";
import Copy from "./components/Copy.jsx";
import Counterparty from "./components/Counterparty.jsx";
import Notes from "./components/Notes.jsx";
import Reading from "./components/Reading.jsx";
import Regions from "./components/Regions.jsx";
import Stamp from "./components/Stamp.jsx";
import Working from "./components/Working.jsx";

/* The three stories a judge should see, in the order that builds the argument.
   Labels say what each is, because this is a guided demo rather than a blind
   test: the interesting part is watching the checks explain themselves. */
const SAMPLES = [
  { kind: "genuine", label: "A genuine invoice", note: "should certify" },
  { kind: "doctored", label: "One with the account changed", note: "caught by the page" },
  { kind: "lookalike", label: "One from a lookalike domain", note: "caught by identity" },
];

const SAMPLE_BRAND = "Northpost Freight Services";

const READING = {
  certified: "Signed by the domain this brand signs from, and the page matches what was signed.",
  flagged: "Something about this document contradicts itself.",
  unsigned:
    "This sender has not published a key, so there is nothing to check against. " +
    "That is a fact about the sender, not a warning about the document.",
};

export default function App() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [brand, setBrand] = useState("");
  const [result, setResult] = useState(null);
  const [live, setLive] = useState(null);
  const [error, setError] = useState(null);
  const [over, setOver] = useState(false);
  /* Every check this session, newest first. Revisiting one costs nothing
     and never re-runs it. Re-checking is deliberately a separate act: the same
     document submitted twice is genuinely a different question, because the
     second time it has been seen before. */
  const [history, setHistory] = useState([]);
  const [resolving, setResolving] = useState(false);
  const [enlarged, setEnlarged] = useState(false);
  const [samples, setSamples] = useState(false);
  const [fetching, setFetching] = useState(null);
  /* The checks that had answered when a run died, kept so a vendor outage
     mid-stream shows what did run rather than pretending nothing happened. */
  const [stopped, setStopped] = useState(null);
  const [adjudicationError, setAdjudicationError] = useState(null);
  const [applied, setApplied] = useState(null);
  const picker = useRef(null);
  const running = useRef(null);
  /* Object URLs live for the whole session, because history keeps pointing at
     them. Revoking one when the preview moves on turned every revisited entry
     into a broken image. They are all released together on unmount. */
  const minted = useRef([]);

  useEffect(
    () => () => {
      running.current?.abort();
      minted.current.forEach((url) => URL.revokeObjectURL(url));
    },
    [],
  );
  useEffect(() => {
    let alive = true;
    verifierHealth().then((health) => {
      if (alive && health?.samples) setSamples(true);
    });
    return () => {
      alive = false;
    };
  }, []);
  /* A drop that misses the target must not navigate the tab away from a run. */
  useEffect(() => {
    const swallow = (event) => event.preventDefault();
    window.addEventListener("dragover", swallow);
    window.addEventListener("drop", swallow);
    return () => {
      window.removeEventListener("dragover", swallow);
      window.removeEventListener("drop", swallow);
    };
  }, []);

  function take(next) {
    if (!next) return;
    running.current?.abort();
    // Cleared so picking the same file again fires a change event.
    if (picker.current) picker.current.value = "";
    const url = URL.createObjectURL(next);
    minted.current.push(url);
    setFile(next);
    setPreview(url);
    setResult(null);
    setLive(null);
    setStopped(null);
    setError(null);
    setApplied(null);
  }

  async function takeSample(kind) {
    if (live || fetching) return;
    setFetching(kind);
    setError(null);
    try {
      const sample = await sampleDocument(kind);
      take(sample);
      // The demo issuer, filled in so the next click is the check itself.
      setBrand(SAMPLE_BRAND);
    } catch (cause) {
      setError(cause.message);
    } finally {
      setFetching(null);
    }
  }

  async function check(event) {
    event.preventDefault();
    if (!file || live) return;
    setError(null);
    setResult(null);
    setStopped(null);
    setApplied(null);
    const controller = new AbortController();
    running.current = controller;

    try {
      const decision = await checkDocument(
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
      if (cause.name !== "AbortError") {
        setError(cause.message);
        setLive((current) => {
          if (current?.signals.length) setStopped(current.signals);
          return current;
        });
      }
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
    setStopped(null);
    setError(null);
    setApplied(null);
  }

  const shown = result;
  const fidelity = shown?.signals.find((signal) => signal.name === "fidelity");
  const signature = shown?.signals.find((signal) => signal.name === "signature");
  const counterparty = shown?.signals.find((signal) => signal.name === "counterparty");
  const issuer = signature?.evidence?.query?.replace(/^_signet\./, "");
  const compared = fidelity?.evidence?.compared ?? [];
  const threshold = fidelity?.evidence?.threshold ?? 0.8;
  const doubted = uncertainFields(fidelity);
  const doubtful =
    fidelity?.outcome === "unknown"
      ? compared.filter((entry) => entry.printed !== null && doubted.has(entry.field))
      : [];

  async function resolve(field, reading) {
    if (!shown) return;
    setResolving(true);
    setAdjudicationError(null);
    try {
      const amended = await adjudicate(shown.runId, field, reading);
      setResult(amended);
      setApplied({ field, reading });
      setHistory((past) =>
        past.map((entry) =>
          entry.id === amended.runId ? { ...entry, decision: amended } : entry,
        ),
      );
    } catch (cause) {
      // Shown beside the panel that asked, not three screens above it.
      setAdjudicationError(cause.message);
    } finally {
      setResolving(false);
    }
  }

  const answered = live?.signals.map((signal) => signal.name) ?? [];
  const waiting = live?.checks.filter((name) => !answered.includes(name)) ?? [];

  return (
    <div className="record">
      <header className="masthead">
        <a className="wordmark" href="/">
          Signet
        </a>
        <span className="label">Document check</span>
      </header>

      <section className="checking">
        <div className="sheet" data-busy={String(Boolean(live))}>
          {preview && file?.type === "application/pdf" ? (
            <div className="sheet-empty">
              <span className="label">PDF document</span>
              <p style={{ margin: 0 }} className="mono">
                {file.name}
              </p>
              <p style={{ margin: 0, color: "var(--muted)" }}>
                The verdict below covers it. The page overlay is drawn for images only.
              </p>
            </div>
          ) : preview ? (
            <>
              <img src={preview} alt="The document being checked" />
              {shown && <Regions compared={compared} fidelity={fidelity} />}
              <button type="button" className="enlarge" onClick={() => setEnlarged(true)}>
                Enlarge
              </button>
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

        <form className="finding" onSubmit={check}>
          {shown ? (
            <>
              <p className="label">The result</p>
              <p className="finding-reason">{shown.reason}</p>
              <p style={{ margin: 0, color: "var(--muted)" }}>
                {shown.verdict === "certified" && fidelity?.outcome === "unknown"
                  ? "Signed by the domain this brand signs from. One reading on the page " +
                    "could not be settled by the machine, so confirm it below."
                  : READING[shown.verdict]}
              </p>
            </>
          ) : live ? (
            <>
              <p className="label">Checking</p>
              <p className="finding-reason">
                {live.signals.length} of {live.checks.length} checks answered.
              </p>
              <p className="skeleton skeleton-line" />
            </>
          ) : (
            <>
              <p className="label">Check a document</p>
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

          {samples && !file && !shown && (
            <div className="samples">
              <span className="label">Nothing to check? Take one of ours</span>
              {SAMPLES.map((sample) => (
                <button
                  key={sample.kind}
                  type="button"
                  className="sample-chip"
                  disabled={Boolean(fetching)}
                  onClick={() => takeSample(sample.kind)}
                >
                  <span>{fetching === sample.kind ? "Signing a fresh one" : sample.label}</span>
                  <span className="mono sample-note">{sample.note}</span>
                </button>
              ))}
              <p className="sample-fine">
                Each one is signed the moment you ask, so it has never been seen before.
              </p>
            </div>
          )}

          <label className="brand-field">
            <span className="label">Who does it claim to be from?</span>
            <input
              value={brand}
              onChange={(event) => setBrand(event.target.value)}
              placeholder="Northpost"
              autoComplete="organization"
            />
          </label>

          <button type="submit" className="run" disabled={!file || Boolean(live)}>
            <span>{live ? "Checking" : "Check this document"}</span>
            <span className="mono run-note">
              {live
                ? checkLabel(live.signals.at(-1)?.name ?? "reading the mark")
                : "reads the key from public DNS"}
            </span>
          </button>

          {error && (
            <p className="mono failure" role="alert">
              {error}
            </p>
          )}
        </form>
      </section>

      {shown && <Notes signals={shown.signals} />}

      {fidelity && <Reading signal={fidelity} />}

      {counterparty && <Counterparty signal={counterparty} />}

      {doubtful.length > 0 && (
        <Adjudicate
          key={shown?.runId}
          fields={doubtful}
          onResolve={resolve}
          busy={resolving}
          failure={adjudicationError}
        />
      )}

      {applied && doubtful.length === 0 && (
        <section className="adjudicate">
          <p className="label">Your reading was applied</p>
          <p className="adjudicate-note">
            The comparison now uses what you read off the page, and the verdict above
            follows from it.
          </p>
        </section>
      )}

      {(shown || live || stopped) && (
        <Working signals={shown?.signals ?? live?.signals ?? stopped ?? []} pending={waiting} />
      )}
      {stopped && !shown && !live && (
        <p className="mono failure" role="alert" style={{ maxWidth: "42rem" }}>
          The run stopped here. The checks above had already answered.
        </p>
      )}

      {history.length > 1 && (
        <section className="history">
          <p className="label">Checked this session</p>
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
                  <span className="label" data-verdict={entry.decision.verdict}>
                    {entry.decision.verdict}
                  </span>
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

      {enlarged && preview && (
        <div
          className="viewer"
          role="dialog"
          aria-modal="true"
          aria-label="The document, enlarged"
          onClick={() => setEnlarged(false)}
        >
          {/* The overlays are positioned as percentages of their container, so
              this box hugs the image here exactly as the small one does. */}
          <div className="viewer-sheet" onClick={(event) => event.stopPropagation()}>
            <img src={preview} alt="The document being checked, enlarged" />
            {shown && <Regions compared={compared} fidelity={fidelity} />}
          </div>
          <button type="button" className="viewer-close" onClick={() => setEnlarged(false)}>
            Close
          </button>
        </div>
      )}
    </div>
  );
}
