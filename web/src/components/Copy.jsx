import { useEffect, useState } from "react";

/** An icon button, which means it needs a name.
 *
 *  The label is the accessible name and the tooltip is the same words, so a
 *  screen reader and a pointer are told the same thing rather than one being an
 *  afterthought. The confirmation replaces the label rather than appearing next
 *  to it, because a control that says what it just did needs no second element.
 */
export default function Copy({ text, label = "Copy" }) {
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!done) return undefined;
    const timer = setTimeout(() => setDone(false), 1600);
    return () => clearTimeout(timer);
  }, [done]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setDone(true);
    } catch {
      setDone(false);
    }
  }

  const name = done ? "Copied" : label;
  return (
    <button type="button" className="icon-button" onClick={copy} aria-label={name} data-tip={name}>
      {done ? (
        <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
          <path d="M3 8.5 6.2 12 13 4.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
        </svg>
      ) : (
        <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
          <rect x="5.5" y="5.5" width="8" height="8" rx="1" fill="none" stroke="currentColor" strokeWidth="1.4" />
          <path d="M10.5 3.5h-8v8" fill="none" stroke="currentColor" strokeWidth="1.4" />
        </svg>
      )}
    </button>
  );
}
