const RECORD = `$ dig +short TXT _signet.northpost.dev

"v=SIGNET1; k=ed25519; p=b5tM2hqtWYdOr3b+3c7yH0fpzDfetg1QKVKldHttwyA="`;

const STEPS = [
  {
    i: "01",
    title: "The issuer publishes a key",
    body: "One Ed25519 public key, written as a TXT record on the domain the business already owns. Nothing is registered with us.",
  },
  {
    i: "02",
    title: "Each document carries a signature",
    body: "The signature covers the fields that move money: the amount, the currency, the account, the document number. It travels in a mark printed on the page.",
  },
  {
    i: "03",
    title: "Anyone checks it",
    body: "Read the mark, fetch the key from DNS, verify. Two commands, no account, and no reason to take our word for any of it.",
  },
];

export default function Landing() {
  return (
    <>
      <section className="hero">
        <h1 className="hero__lede">
          A perfect invoice and a <em>genuine</em> invoice are now the same picture.
        </h1>
        <p className="hero__sub">
          Detection asks whether a document looks fake, and that question stopped working the
          moment anyone could generate a flawless one. Signet asks a different question: can the
          business it names prove it sent this? That answer does not degrade as the forgeries
          improve.
        </p>
        <p className="hero__act">
          <a className="press" href="#/verify">Examine a document</a>
          <a className="press press--ghost" href="#proof">See the proof</a>
        </p>
      </section>

      <section className="figures">
        <div className="figure figure--bad">
          <p className="figure__n">71%</p>
          <p>
            of flagged fake documents were machine generated, up from none fourteen months
            earlier. The tooling to forge got cheap faster than the tooling to detect.
          </p>
        </div>
        <div className="figure figure--odd">
          <p className="figure__n">1 in 8</p>
          <p>
            authentic documents are wrongly flagged by detection tools. A verdict that accuses
            real suppliers is not one a finance team can act on.
          </p>
        </div>
      </section>

      <section className="steps">
        <h2 className="cap">How the proof works</h2>
        <ol className="steps__list">
          {STEPS.map((step) => (
            <li className="step" key={step.i}>
              <span className="step__i">{step.i}</span>
              <h3>{step.title}</h3>
              <p>{step.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="proof" id="proof">
        <h2>The trust root is the issuer&rsquo;s domain, not our database.</h2>
        <p>
          This is a real key, live in public DNS right now. Run it yourself. If our service
          disappeared tomorrow, every document already issued would still verify, because the
          proof was never held here.
        </p>
        <pre className="slab">{RECORD}</pre>
        <p>
          A forger can register a lookalike domain and sign their own invoice perfectly well. The
          signature will verify. It will still fail, because the brand named on the paper does not
          sign from that domain.
        </p>
      </section>
    </>
  );
}
