const MARK = { pass: "✓", fail: "✕", unknown: "?" };

/** Each check as an exchange: what was asked, what came back.
 *
 *  Prose would be shorter. The point of this product is that you do not have to
 *  believe the sentence, so the query and the answer are the content and the
 *  sentence is the summary. */
function exchange(name, evidence) {
  if (!evidence || Object.keys(evidence).length === 0) return [];

  if (name === "signature") {
    const rows = [["asked", `${evidence.query}  TXT`]];
    for (const [resolver, records] of Object.entries(evidence.answers ?? {})) {
      rows.push([resolver, records.length ? records[0] : "no answer"]);
    }
    if (evidence.reached) {
      rows.push([
        "agreement",
        evidence.resolversAgreed
          ? "both resolvers returned the same record"
          : "resolvers disagreed, which can mean a spoofed answer",
      ]);
      rows.push(["dnssec", evidence.dnssecValidated ? "validated chain" : "unsigned zone (advisory)"]);
    }
    if (evidence.signedBytes) rows.push(["signed bytes", evidence.signedBytes]);
    return rows;
  }

  if (name === "identity") {
    return [
      ["document names", evidence.claimedBrand ?? "no brand given"],
      ["signed by", evidence.domain],
      ["that domain is", evidence.enrolledBrand ?? "not enrolled"],
    ];
  }

  if (name === "lookalike" && evidence.comparedAgainst) {
    return [
      ["signing domain", evidence.domain],
      ["brand signs from", evidence.comparedAgainst],
    ];
  }

  if (name === "duplicate") {
    return [["fingerprint", evidence.fingerprint]];
  }

  if (name === "domain_age" && evidence.created) {
    return [
      ["registered", evidence.created],
      ["age", `${evidence.ageDays} days`],
    ];
  }

  if (name === "fidelity" && evidence.compared) {
    return evidence.compared.map((field) => [
      field.field,
      field.printed === null
        ? `signed as ${field.signed}, not printed on the page`
        : field.agrees
          ? `${field.printed}  matches what was signed`
          : `page shows ${field.printed}, signature covers ${field.signed}`,
    ]);
  }

  return [];
}

export default function Working({ signals }) {
  return (
    <section className="working">
      <p className="working-note">
        Each check, and what it saw. Nothing here is a summary of a summary.
      </p>
      {signals.map((signal) => {
        const rows = exchange(signal.name, signal.evidence);
        return (
          <article className="check" key={signal.name}>
            <span className="check-outcome" data-outcome={signal.outcome} aria-label={signal.outcome}>
              {MARK[signal.outcome]}
            </span>
            <span className="check-name">{signal.name.replace("_", " ")}</span>
            <div className="check-body">
              <p className="check-detail">{signal.detail}</p>
              {rows.length > 0 && (
                <dl className="exchange">
                  {rows.map(([term, value]) => (
                    <div key={term} style={{ display: "contents" }}>
                      <dt>{term}</dt>
                      <dd>{value}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </div>
          </article>
        );
      })}
    </section>
  );
}
