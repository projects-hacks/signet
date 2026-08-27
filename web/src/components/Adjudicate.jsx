import { useState } from "react";

/** The question the extractor could not answer, put to a person.
 *
 *  They are shown the field, what the extractor thought it said, how sure it
 *  was, and where on the page it looked. They type what the page actually says.
 *
 *  What they are not shown is the signed value, and that is deliberate. Somebody
 *  reading a page with the expected answer in front of them is being led, and a
 *  reading produced that way is not evidence of anything. They read the page;
 *  the comparison is ours. */
export default function Adjudicate({ fields, onResolve, busy }) {
  const [readings, setReadings] = useState({});

  if (!fields.length) return null;

  return (
    <section className="adjudicate">
      <p className="label">The extractor is not sure</p>
      <p className="adjudicate-note">
        {fields.length === 1
          ? "One field could not be read confidently."
          : `${fields.length} fields could not be read confidently.`}{" "}
        Read it off the page above and type what it says. The verdict follows from
        your reading the same way it would have followed from a clean one.
      </p>

      {fields.map((field) => (
        <form
          className="doubtful"
          key={field.field}
          onSubmit={(event) => {
            event.preventDefault();
            const reading = (readings[field.field] ?? field.printed ?? "").trim();
            if (reading) onResolve(field.field, reading);
          }}
        >
          <div className="doubtful-head">
            <span className="check-name">{field.field.replace("_", " ")}</span>
            <span className="mono confidence">
              {Math.round((field.confidence ?? 0) * 100)}% confident
            </span>
          </div>
          <p className="mono machine-read">
            read as <b>{field.printed}</b>
          </p>
          <div className="doubtful-answer">
            <label>
              <span className="label">What does the page say?</span>
              <input
                defaultValue={field.printed ?? ""}
                onChange={(event) =>
                  setReadings((current) => ({ ...current, [field.field]: event.target.value }))
                }
                spellCheck="false"
                autoComplete="off"
              />
            </label>
            <button type="submit" className="confirm" disabled={busy}>
              {busy ? "Applying" : "Confirm reading"}
            </button>
          </div>
        </form>
      ))}
    </section>
  );
}
