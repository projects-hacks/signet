/** Every field the extractor read, drawn where it read it.
 *
 *  Showing the fields that matched is what makes the one that did not mean
 *  something: a lone red box could be anything, a red box among green ones is
 *  a discrepancy. Boxes arrive as percentages of the page, so they scale with
 *  whatever width the sheet ends up at. */
export default function Regions({ compared, threshold }) {
  return compared
    .filter((field) => field.box)
    .map((field) => {
      const uncertain = field.confidence < threshold;
      // A label to the right of a value near the right margin would hang off
      // the sheet, so those flip to the other side.
      // A value normally has whitespace after it, so the label goes there. Near
      // the right margin there is none, and putting it on the left instead sets
      // it over the words in front of the value. Those go above.
      const side = field.box.left + field.box.width > 0.66 ? "above" : "right";
      // The extractor returns a box tight to the glyphs, and a border drawn on
      // that line reads as a strikethrough over the value it is confirming.
      const pad = 0.004;
      return (
        <div
          key={field.field}
          className="region"
          data-agrees={String(field.agrees)}
          data-uncertain={String(uncertain)}
          data-side={side}
          style={{
            left: `${(field.box.left - pad / 2) * 100}%`,
            top: `${(field.box.top - pad) * 100}%`,
            width: `${(field.box.width + pad) * 100}%`,
            height: `${(field.box.height + pad * 2) * 100}%`,
          }}
        >
          <span className="region-tag">{field.field}</span>
        </div>
      );
    });
}
