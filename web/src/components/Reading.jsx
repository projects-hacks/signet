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
import { fieldLabel, uncertainFields } from "../labels.js";

export default function Reading({ signal }) {
  const compared = signal?.evidence?.compared;
  if (!Array.isArray(compared) || compared.length === 0) return null;

  const threshold = signal.evidence.threshold ?? 0.8;
  // A grounding score is the same for every field it anchors, so a meter of
  // identical bars is the expected shape rather than a fault.
  const scores = compared.map((field) => field.confidence).filter((c) => typeof c === "number");
  const uniform = scores.length > 1 && new Set(scores).size === 1;
  const doubted = uncertainFields(signal);
  const doubtful = compared.filter(
    (field) => field.printed !== null && doubted.has(field.field),
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
              const unsure = !unread && doubted.has(field.field);
              return (
                <tr
                  key={field.field}
                  data-unsure={String(unsure)}
                  data-agrees={String(unread || unsure || field.agrees)}
                >
                  <td className="reading-field">{fieldLabel(field.field)}</td>
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
                  <td className="mono">
                    {field.signed === null || field.signed === undefined ? (
                      <span className="reading-absent">
                        withheld until you read the page
                      </span>
                    ) : (
                      field.signed
                    )}
                  </td>
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
          ? `A reading below ${Math.round(threshold * 100)}% confidence, or one that cannot ` +
            `be a real value for its field, is not trusted, and ` +
            `${doubtful === 1 ? "one field is" : `${doubtful} fields are`} put to a person ` +
            "rather than guessed at."
          : "Every field was read cleanly, so the comparison above stands on its own."}
      </p>
      {/* Five identical bars read as a broken meter unless the number is
          named. The extractor reports a grounding score when the model returns
          no token probabilities, so anything it anchors in the page scores the
          same. Saying so is also why the shape of a value is checked and not
          only its score. */}
      {uniform && (
        <p className="reading-note">
          Every reading scores the same because the extractor is reporting whether it found the
          value anchored in the page, not how legible the page was. That is why a value is checked
          against the shape its field can hold as well as against this score.
        </p>
      )}
    </section>
  );
}
