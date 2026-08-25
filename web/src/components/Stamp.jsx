const HUE = {
  certified: "var(--verify)",
  flagged: "var(--refuse)",
  unsigned: "var(--doubt)",
};

/** The verdict, pressed onto the document rather than sitting beside it.
 *  Its colour is the verdict, so the boldest mark on the page carries meaning. */
export default function Stamp({ verdict, issuer }) {
  return (
    <div className="stamp" style={{ "--verdict": HUE[verdict] ?? "var(--doubt)" }}>
      <span className="stamp-verdict">{verdict}</span>
      {issuer ? <span className="stamp-issuer">{issuer}</span> : null}
    </div>
  );
}
