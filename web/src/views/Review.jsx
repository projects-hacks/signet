// The review queue.
//
// Extraction already returns a confidence and a bounding box for every field it
// reads, and the fidelity check already routes a field it could not read
// confidently to a human. Nothing yet catches that handoff, so this view is
// honest about being empty rather than showing invented rows.
export default function Review() {
  return (
    <>
      <section className="steps">
        <h2 className="cap">Review queue</h2>
        <p style={{ maxWidth: "64ch", color: "var(--ink-soft)" }}>
          When the page and the signature disagree, or a field cannot be read confidently, the
          document is not refused and it is not waved through. It waits here for a person, with
          the disputed value boxed on the page beside the value that was signed.
        </p>
      </section>
      <p className="blank">Nothing is waiting for a decision.</p>
    </>
  );
}
