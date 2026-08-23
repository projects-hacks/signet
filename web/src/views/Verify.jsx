import { useRef, useState } from "react";
import Ledger from "../components/Ledger.jsx";
import Seal from "../components/Seal.jsx";

const ACCEPT = "image/png,image/jpeg,image/webp,application/pdf";

function issuerFrom(signals) {
  const signature = signals.find((signal) => signal.name === "signature");
  const found = signature && signature.detail.match(/by ([a-z0-9.-]+\.[a-z]{2,})/i);
  return found ? found[1] : "<issuer>";
}

export default function Verify() {
  const input = useRef(null);
  const [file, setFile] = useState(null);
  const [brand, setBrand] = useState("");
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [failure, setFailure] = useState(null);

  const examine = async (event) => {
    event.preventDefault();
    if (!file || busy) return;
    setBusy(true);
    setFailure(null);

    const body = new FormData();
    body.append("file", file);
    if (brand.trim()) body.append("brand", brand.trim());

    try {
      const response = await fetch("/api/verify", { method: "POST", body });
      const data = await response.json();
      if (response.ok) setResult(data);
      else {
        setResult(null);
        setFailure(data.error || "That document could not be examined.");
      }
    } catch {
      setResult(null);
      setFailure("The examiner is not reachable. Check that the server is running.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <form className="counter" onSubmit={examine}>
        <div className="counter__row">
          <div className="field">
            <label className="cap" htmlFor="file">Document</label>
            <button
              type="button"
              className="drop"
              data-over={over || undefined}
              data-has={file ? "true" : undefined}
              onClick={() => input.current.click()}
              onDragOver={(e) => { e.preventDefault(); setOver(true); }}
              onDragLeave={() => setOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setOver(false);
                if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
              }}
            >
              <span className="drop__name">{file ? file.name : "No document yet"}</span>
              <span className="drop__hint">Choose a file, or drop one here</span>
            </button>
            <input
              ref={input}
              id="file"
              type="file"
              accept={ACCEPT}
              hidden
              onChange={(e) => e.target.files[0] && setFile(e.target.files[0])}
            />
          </div>

          <div className="field">
            <label className="cap" htmlFor="brand">Meant to be from</label>
            <input
              id="brand"
              className="brand"
              type="text"
              placeholder="Northpost"
              autoComplete="organization"
              value={brand}
              onChange={(e) => setBrand(e.target.value)}
            />
          </div>

          <button className="press" type="submit" disabled={!file || busy}>
            {busy ? "Examining" : "Examine"}
          </button>
        </div>
      </form>

      {failure && (
        <div className="result" data-verdict="unsigned">
          <Seal runId="none" verdict="unsigned" word="no answer" />
          <p className="result__reason">{failure}</p>
        </div>
      )}

      {result && !failure && (
        <div className="result" data-verdict={result.verdict}>
          <Seal runId={result.runId} verdict={result.verdict} />
          <p className="result__reason">{result.reason}</p>
          <Ledger signals={result.signals} />
          <p className="trace">
            Run <span className="mono">{result.runId}</span>. Check the key yourself:{" "}
            <span className="mono">dig +short TXT _signet.{issuerFrom(result.signals)}</span>
          </p>
        </div>
      )}

      {!result && !failure && (
        <p className="blank">A document carries its own proof. Examine one.</p>
      )}
    </>
  );
}
