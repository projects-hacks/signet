import Evidence from "./Evidence.jsx";

const GLYPH = { pass: "✓", fail: "✕", unknown: "?" };

// Check names are internal. A reader gets the plain noun.
const LABEL = {
  signature: "Signature",
  identity: "Identity",
  lookalike: "Lookalike",
  duplicate: "Duplicate",
  domain_age: "Domain age",
  fidelity: "Fidelity",
};

export default function Ledger({ signals }) {
  return (
    <ol className="ledger">
      {signals.map((signal) => {
        const hasWorking = signal.evidence && Object.keys(signal.evidence).length > 0;
        return (
          <li key={signal.name} data-outcome={signal.outcome}>
            <span className="ledger__glyph" aria-hidden="true">
              {GLYPH[signal.outcome] || "?"}
            </span>
            <div className="ledger__what">
              <b>{LABEL[signal.name] || signal.name}</b>
              <span>{signal.detail}</span>
              {hasWorking && (
                <details className="working">
                  <summary>Show the working</summary>
                  <Evidence evidence={signal.evidence} />
                </details>
              )}
            </div>
            <span className="ledger__from">{signal.source}</span>
          </li>
        );
      })}
    </ol>
  );
}
