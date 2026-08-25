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
      return (
        <div
          key={field.field}
          className="region"
          data-agrees={String(field.agrees)}
          data-uncertain={String(uncertain)}
          style={{
            left: `${field.box.left * 100}%`,
            top: `${field.box.top * 100}%`,
            width: `${field.box.width * 100}%`,
            height: `${field.box.height * 100}%`,
          }}
        >
          <span className="region-tag">{field.field}</span>
        </div>
      );
    });
}
