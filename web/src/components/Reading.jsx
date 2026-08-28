/** What the extractor read, how sure it was, and what it was compared against.
 *
 *  The fidelity check reduces to one sentence, which is right for a verdict and
 *  wrong for understanding it. This is the working: every payment field the
 *  signature covers, what was read off the page as it actually arrived, the
 *  confidence that reading carries, and whether the two agree.
 *
 *  The confidence is shown as a number rather than a colour alone, because the
 *  whole argument of this check is that a machine reading has a measurable
 *  quality and a person should see it before trusting a comparison built on it.
 */
export default function Reading({ signal }) {
  const compared = signal?.evidence?.compared;
  if (!Array.isArray(compared) || compared.length === 0) return null;

  const threshold = signal.evidence.threshold ?? 0.8;
  const doubtful = compared.filter(
    (field) => field.printed !== null && (field.confidence ?? 1) < threshold,
  ).length;

  return (
    <section className="reading" data-outcome={signal.outcome}>
      <p className="label">What the page actually says</p>
      <p className="reading-lede">{signal.detail}</p>

      <div className="scroller">
        <table className="reading-table">
          <thead>
            <tr>
              <th>Field</th>
              <th>Read off the page</th>
              <th>Confidence</th>
              <th>Covered by the signature</th>
              <th aria-label="agreement" />
            </tr>
          </thead>
          <tbody>
            {compared.map((field) => {
              const confidence = field.confidence ?? null;
              const unread = field.printed === null;
              const unsure = !unread && confidence !== null && confidence < threshold;
              return (
                <tr key={field.field} data-unsure={String(unsure)}>
                  <td className="reading-field">{field.field.replace("_", " ")}</td>
                  <td className="mono">
                    {unread ? <span className="reading-absent">not on the page</span> : field.printed}
                  </td>
                  <td>
                    {confidence === null || unread ? (
                      <span className="reading-absent">not read</span>
                    ) : (
                      <span className="meter" title={`${Math.round(confidence * 100)}%`}>
                        <i style={{ width: `${Math.round(confidence * 100)}%` }} />
                        <b>{Math.round(confidence * 100)}%</b>
                      </span>
                    )}
                  </td>
                  <td className="mono">{field.signed}</td>
                  <td className="reading-verdict">
                    {unread ? "" : unsure ? "?" : field.agrees ? "✓" : "✕"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="reading-note">
        {doubtful > 0
          ? `Below ${Math.round(threshold * 100)}% the reading is not trusted, and ` +
            `${doubtful === 1 ? "one field is" : `${doubtful} fields are`} put to a person ` +
            "rather than guessed at."
          : `Every field was read above ${Math.round(threshold * 100)}% confidence, so the ` +
            "comparison above stands on its own."}
      </p>
    </section>
  );
}
