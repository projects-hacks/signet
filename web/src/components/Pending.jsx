/** The shape of the answer, before the answer.
 *
 *  A skeleton earns its place only by matching the layout it stands in for. This
 *  one is the same three column check row the real result uses, with the check's
 *  real name already in place, because the name is known the moment the run
 *  starts and pretending otherwise would be animation rather than information.
 *
 *  There is no shimmer that loops forever. A stalled run shows an error, because
 *  a skeleton that keeps breathing through a failure is a lie about the state.
 */
export default function Pending({ names }) {
  return (
    <>
      {names.map((name) => (
        <article className="check is-pending" key={name} aria-hidden="true">
          <span className="check-outcome" data-outcome="pending" />
          <span className="check-name">{name.replace("_", " ")}</span>
          <div className="check-body">
            <p className="skeleton skeleton-line" />
            <p className="skeleton skeleton-line is-short" />
          </div>
        </article>
      ))}
    </>
  );
}
