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
      {signals.map((signal) => (
        <li key={signal.name} data-outcome={signal.outcome}>
          <span className="ledger__glyph" aria-hidden="true">{GLYPH[signal.outcome] || "?"}</span>
          <span className="ledger__what">
            <b>{LABEL[signal.name] || signal.name}</b>
            <span>{signal.detail}</span>
          </span>
          <span className="ledger__from">{signal.source}</span>
        </li>
      ))}
    </ol>
  );
}
