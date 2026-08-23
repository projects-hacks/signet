// What a check actually saw.
//
// The finding is the sentence a reader acts on. This is the material underneath
// it, shown so the claim can be inspected rather than believed. Two independent
// resolvers are printed separately because agreement between them is the thing
// that makes a spoofed answer expensive, and agreement asserted is worth less
// than agreement shown.

function Row({ label, children }) {
  return (
    <div className="ev__row">
      <span className="ev__k">{label}</span>
      <span className="ev__v">{children}</span>
    </div>
  );
}

function Answers({ answers, agreed }) {
  const providers = Object.entries(answers || {});
  if (!providers.length) return null;
  return (
    <div className="ev__row">
      <span className="ev__k">Resolvers</span>
      <span className="ev__v">
        {providers.map(([who, records]) => (
          <span className="ev__answer" key={who}>
            <b>{who}</b>
            {records.length ? (
              records.map((record) => <code key={record}>{record}</code>)
            ) : (
              <code className="ev__none">no answer</code>
            )}
          </span>
        ))}
        <span className={agreed ? "ev__agree" : "ev__disagree"}>
          {agreed ? "Both answered alike" : "Answers differ, which can mean a spoofed reply"}
        </span>
      </span>
    </div>
  );
}

// Rendered above in a shape a reader can act on, so the generic pass skips them.
const SKIP = new Set(["answers", "resolversAgreed", "signedBytes", "signature", "query"]);

export default function Evidence({ evidence }) {
  if (!evidence || !Object.keys(evidence).length) return null;
  const rest = Object.entries(evidence).filter(([key]) => !SKIP.has(key));

  return (
    <div className="ev">
      {evidence.query && <Row label="Query">{`dig +short TXT ${evidence.query}`}</Row>}
      <Answers answers={evidence.answers} agreed={evidence.resolversAgreed} />

      {evidence.signedBytes && (
        <Row label="Bytes signed">
          <code className="ev__bytes">{evidence.signedBytes}</code>
        </Row>
      )}
      {evidence.signature && (
        <Row label="Signature">
          <code className="ev__bytes">{evidence.signature}</code>
        </Row>
      )}

      {rest.map(([key, value]) => (
        <Row key={key} label={key.replace(/([A-Z])/g, " $1").replace(/^./, (c) => c.toUpperCase())}>
          {typeof value === "boolean" ? (value ? "yes" : "no") : String(value)}
        </Row>
      ))}
    </div>
  );
}
