/** What did not change the verdict, but that a reader should still know.
 *
 *  The headline names the single most consequential finding, which is right:
 *  a reader deciding whether to pay needs one sentence, not seven. But a
 *  document can be flagged as a duplicate while also having been signed by a
 *  domain registered six days ago, and showing only the first is a true
 *  summary that leaves out the thing that would actually change somebody's
 *  mind.
 *
 *  Two kinds of unknown are separated here, because they mean opposite things
 *  and the verdict engine deliberately does not distinguish them. A check that
 *  ran and found something advisory carries its evidence. A check that could
 *  not reach its evidence carries none, and its source holds the reason. That
 *  discriminator already exists in the data, so no new outcome was needed. */
export default function Notes({ signals }) {
  const unknown = signals.filter((signal) => signal.outcome === "unknown");
  const found = unknown.filter((signal) => Object.keys(signal.evidence ?? {}).length > 0);
  const unreachable = unknown.filter(
    (signal) => Object.keys(signal.evidence ?? {}).length === 0,
  );

  if (!found.length && !unreachable.length) return null;

  return (
    <section className="notes">
      {found.length > 0 && (
        <>
          <p className="label">Worth knowing, though none of it decided the verdict</p>
          <ul className="notes-list">
            {found.map((signal) => (
              <li key={signal.name}>
                <span className="notes-name">{signal.name.replace("_", " ")}</span>
                <span>{signal.detail}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      {unreachable.length > 0 && (
        <p className="notes-gap">
          <b>
            {unreachable.length === 1
              ? "One check could not run"
              : `${unreachable.length} checks could not run`}
          </b>{" "}
          ({unreachable.map((signal) => signal.name.replace("_", " ")).join(", ")}). A
          check that cannot reach its evidence never passes, so the verdict above
          reflects less than it otherwise would rather than more.
        </p>
      )}
    </section>
  );
}
