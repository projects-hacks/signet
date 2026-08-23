// The guilloche.
//
// This is the interference pattern engraved into banknotes and share
// certificates, used there precisely because a lathe-cut curve is hard to
// reproduce by hand. Here it is plotted from the run's own identifier, so one
// document always strikes one seal and two documents never strike the same one.
// It is a fingerprint you can see, making the same claim the signature makes in
// bytes.
//
// The centre is cleared rather than filled, because a struck seal carries its
// ornament around a clear field, and because the verdict has to be readable.

const RINGS = 5;
const SPAN_MS = 1100;

/* Deterministic, so the same run always draws the same seal. */
function seedOf(text) {
  let h = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return () => {
    h ^= h << 13;
    h ^= h >>> 17;
    h ^= h << 5;
    return ((h >>> 0) % 100000) / 100000;
  };
}

function ringsFrom(seed) {
  return Array.from({ length: RINGS }, (_, i) => ({
    R: 0.5 + seed() * 0.34,
    r: 0.06 + seed() * 0.11,
    d: 0.1 + seed() * 0.2,
    scale: 1 - i * 0.07,
    turns: 22 + Math.floor(seed() * 26),
  }));
}

export function drawRosette(canvas, runId, verdict, { animate = true } = {}) {
  const ctx = canvas.getContext("2d");
  const size = canvas.width;
  const mid = size / 2;
  const rings = ringsFrom(seedOf(runId || "none"));
  const styles = getComputedStyle(document.body);
  const token =
    verdict === "flagged" ? "--struck" : verdict === "unsigned" ? "--gold" : "--seal";
  const ink = styles.getPropertyValue(token).trim();
  const paper = styles.getPropertyValue("--paper-deep").trim();

  const plot = (ring, upTo) => {
    const base = mid * 0.9 * ring.scale;
    const steps = ring.turns * 90;
    ctx.beginPath();
    for (let i = 0; i <= steps * upTo; i += 1) {
      const t = (i / 90) * Math.PI * 2;
      const k = (ring.R - ring.r) / ring.r;
      const x = mid + base * ((ring.R - ring.r) * Math.cos(t) + ring.d * Math.cos(k * t));
      const y = mid + base * ((ring.R - ring.r) * Math.sin(t) - ring.d * Math.sin(k * t));
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  };

  const circle = (radius, width) => {
    ctx.lineWidth = width;
    ctx.beginPath();
    ctx.arc(mid, mid, mid * radius, 0, Math.PI * 2);
    ctx.stroke();
    ctx.lineWidth = 0.7;
  };

  const field = () => {
    ctx.fillStyle = paper;
    ctx.beginPath();
    ctx.arc(mid, mid, mid * 0.54, 0, Math.PI * 2);
    ctx.fill();
    circle(0.54, 1.2);
  };

  /* A cancelled instrument is struck through, not recoloured. */
  const cancel = () => {
    if (verdict !== "flagged") return;
    ctx.lineWidth = 6;
    ctx.globalAlpha = 0.85;
    ctx.beginPath();
    ctx.moveTo(size * 0.12, size * 0.76);
    ctx.lineTo(size * 0.88, size * 0.24);
    ctx.stroke();
    ctx.globalAlpha = 1;
    ctx.lineWidth = 0.7;
  };

  const paint = (progress) => {
    ctx.clearRect(0, 0, size, size);
    ctx.strokeStyle = ink;
    ctx.lineWidth = 0.7;
    circle(0.97, 1.4);
    rings.forEach((ring, index) => {
      const from = index / RINGS;
      const local = Math.max(0, Math.min((progress - from) * RINGS, 1));
      if (local > 0) plot(ring, local);
    });
    field();
    if (progress >= 1) cancel();
  };

  if (!animate) {
    paint(1);
    return () => {};
  }

  let frame = 0;
  const started = performance.now();
  const step = (now) => {
    const progress = Math.min((now - started) / SPAN_MS, 1);
    paint(progress);
    if (progress < 1) frame = requestAnimationFrame(step);
  };
  frame = requestAnimationFrame(step);
  return () => cancelAnimationFrame(frame);
}
