/** What the open web says about the party asking to be paid.
 *
 *  This is the only check that can catch somebody impersonating a company that
 *  never enrolled with anyone, which is most companies. Every other check
 *  compares the document against records we already hold, and is therefore
 *  silent about a brand it has never heard of.
 *
 *  It gets its own panel rather than a row in the table because it is the one
 *  answer that came from outside the system, and because the sources are worth
 *  following. A reader who does not believe us can click them. */
export default function Counterparty({ signal }) {
  if (!signal?.evidence?.brand) return null;

  const { brand, signingDomain, publishedDomain, adverseMentions = [], sources = [] } =
    signal.evidence;
  const agrees = publishedDomain && signingDomain && publishedDomain === signingDomain;

  return (
    <section className="counterparty" data-outcome={signal.outcome}>
      <p className="label">Live diligence</p>
      <p className="counterparty-lede">{signal.detail}</p>

      <dl className="counterparty-facts">
        <div>
          <dt>The document claims</dt>
          <dd>{brand}</dd>
        </div>
        <div>
          <dt>It was signed by</dt>
          <dd className="mono">{signingDomain}</dd>
        </div>
        <div>
          <dt>The open web publishes</dt>
          <dd className="mono" data-agrees={String(Boolean(agrees))}>
            {publishedDomain ?? "no domain it will vouch for"}
          </dd>
        </div>
      </dl>

      {adverseMentions.length > 0 && (
        <div className="adverse">
          <p className="label">Other uses of this name, for you to judge</p>
          <ul>
            {adverseMentions.map((mention) => (
              <li key={mention}>{mention}</li>
            ))}
          </ul>
          <p className="adverse-note">
            A name search returns every company with a similar name. These are shown
            because a person should see them, not because they count against this
            document.
          </p>
        </div>
      )}

      {sources.length > 0 && (
        <p className="counterparty-sources">
          Checked against{" "}
          {sources.slice(0, 4).map((source, index) => (
            <span key={source}>
              {index > 0 && ", "}
              <a href={source} rel="noreferrer noopener">
                {hostOf(source)}
              </a>
            </span>
          ))}
          . Searched live, not from a list we keep.
        </p>
      )}
    </section>
  );
}

function hostOf(source) {
  try {
    return new URL(source).hostname.replace(/^www\./, "");
  } catch {
    return source;
  }
}
