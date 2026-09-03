/** Every field the extractor read, drawn where it read it.
 *
 *  Showing the fields that matched is what makes the one that did not mean
 *  something: a lone red box could be anything, a red box among green ones is
 *  a discrepancy. Boxes arrive as percentages of the page, so they scale with
 *  whatever width the sheet ends up at. */
import { fieldLabel, uncertainFields } from "../labels.js";

export default function Regions({ compared, fidelity }) {
  const doubted = uncertainFields(fidelity);
  const drawn = compared.filter((field) => field.box);
  // Labels above their box sit on one line, and two boxes side by side on a
  // totals row are far closer together than their labels are wide, so the
  // second prints over the first. Ordering them left to right and lifting each
  // one clear of the last gives every label its own line.
  const lifted = new Map();
  drawn
    .filter((field) => field.box.left + field.box.width > 0.66)
    .sort((a, b) => a.box.left - b.box.left)
    .forEach((field, index, all) => {
      const previous = all[index - 1];
      const crowded = previous && field.box.left - previous.box.left < 0.14;
      lifted.set(field.field, crowded ? (lifted.get(previous.field) ?? 0) + 1 : 0);
    });

  return drawn
    .map((field) => {
      const uncertain = doubted.has(field.field);
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
            "--lift": lifted.get(field.field) ?? 0,
            left: `${(field.box.left - pad / 2) * 100}%`,
            top: `${(field.box.top - pad) * 100}%`,
            width: `${(field.box.width + pad) * 100}%`,
            height: `${(field.box.height + pad * 2) * 100}%`,
          }}
        >
          <span className="region-tag">{fieldLabel(field.field)}</span>
        </div>
      );
    });
}
