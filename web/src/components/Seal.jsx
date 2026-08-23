import { useEffect, useRef } from "react";
import { drawRosette } from "../lib/rosette.js";

// The seal is struck once per run. Redrawing it on every render would restart
// the engraving, so it is keyed to the run and nothing else.
export default function Seal({ runId, verdict, word }) {
  const canvas = useRef(null);

  useEffect(() => {
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    return drawRosette(canvas.current, runId, verdict, { animate: !still });
  }, [runId, verdict]);

  return (
    <figure className="impression">
      <canvas ref={canvas} width="620" height="620" aria-hidden="true" />
      <figcaption className="impression__word">{word || verdict}</figcaption>
    </figure>
  );
}
