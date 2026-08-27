/* Motion that carries information, and nothing that does not.

   Three things move on this page. The stamp lands, because a verdict arriving
   is the product. The terminal types, because the claim is that two commands
   are enough and showing them run is stronger than printing them. Sections
   settle in as they arrive, because a long page reads better arriving in
   pieces. Everything else is still. */

const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/* ── the stamp, and the pins that point at the page ──────────────── */

const exhibit = document.querySelector("[data-stamp]");
if (exhibit) {
  const land = () => exhibit.classList.add("is-stamped");
  if (still) {
    land();
  } else {
    const watcher = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setTimeout(land, 420);
            watcher.disconnect();
          }
        }
      },
      { threshold: 0.35 },
    );
    watcher.observe(exhibit);
  }
}

/* ── the terminal ────────────────────────────────────────────────── */

/* Two runs of the same command against the same document, one of which had a
   single digit changed. The second is the point: the first only proves the
   tool says yes. */
const SESSION = [
  { text: "dig +short TXT _signet.northpost.dev", kind: "cmd" },
  { text: '"v=SIGNET1; k=ed25519; p=Kqf0GFh29fslh099Tr9ruRvy6qI7ITeKC5KY8Wt0YWI="', kind: "out" },
  { text: "", kind: "gap" },
  { text: "openssl pkeyutl -verify -pubin -inkey pub.pem \\", kind: "cmd" },
  { text: "    -rawin -in payload.txt -sigfile sig.bin", kind: "cont" },
  { text: "Signature Verified Successfully", kind: "good" },
  { text: "", kind: "gap" },
  { text: "# now change one digit of the amount", kind: "note" },
  { text: "sed 's/15580.00/15580.01/' payload.txt > tampered.txt", kind: "cmd" },
  { text: "openssl pkeyutl -verify -pubin -inkey pub.pem \\", kind: "cmd" },
  { text: "    -rawin -in tampered.txt -sigfile sig.bin", kind: "cont" },
  { text: "Signature Verification Failure", kind: "bad" },
];

const CLASS = { cmd: "line cmd", cont: "line cmd", out: "line", good: "line good", bad: "line bad", note: "line note", gap: "line gap" };
const TYPE_MS = 14;
const PAUSE_MS = 340;
const REPLAY_MS = 6000;

const screen = document.querySelector("[data-script]");

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function play() {
  screen.textContent = "";
  for (const step of SESSION) {
    const line = document.createElement("span");
    line.className = CLASS[step.kind];
    screen.append(line);
    if (step.kind === "gap") continue;

    // Typed only where a person would be typing. Output arrives at once,
    // because a machine printing a result character by character is theatre.
    if (step.kind === "cmd" || step.kind === "cont") {
      if (step.kind === "cmd") {
        const mark = document.createElement("i");
        mark.textContent = "$ ";
        line.append(mark);
      }
      for (const character of step.text) {
        line.append(character);
        await sleep(TYPE_MS);
      }
    } else {
      line.append(step.text);
    }
    await sleep(PAUSE_MS);
  }
}

if (screen) {
  if (still) {
    for (const step of SESSION) {
      const line = document.createElement("span");
      line.className = CLASS[step.kind];
      line.textContent = step.kind === "cmd" || step.kind === "cont" ? `$ ${step.text}` : step.text;
      screen.append(line);
    }
  } else {
    let running = false;
    const loop = async () => {
      running = true;
      // The whole session repeats rather than freezing on the last frame, so a
      // reader who scrolled past and came back still sees it run.
      // eslint-disable-next-line no-constant-condition
      while (true) {
        await play();
        await sleep(REPLAY_MS);
      }
    };
    const watcher = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting && !running) loop();
        }
      },
      { threshold: 0.3 },
    );
    watcher.observe(document.querySelector("[data-terminal]"));
  }
}

/* ── numbers, counted up ─────────────────────────────────────────

   The figures are the argument, so they are worth a moment of attention. The
   count runs once, lands on the exact printed value, and the element already
   holds that value in the markup, so a reader with motion turned off or with
   the script blocked sees the real number rather than a zero. */

const COUNT_MS = 900;

function countUp(element) {
  const target = Number(element.dataset.count);
  if (!Number.isFinite(target)) return;
  const prefix = element.dataset.prefix ?? "";
  const suffix = element.dataset.suffix ?? "";
  const decimals = (String(target).split(".")[1] ?? "").length;
  const started = performance.now();

  const step = (now) => {
    const through = Math.min(1, (now - started) / COUNT_MS);
    // Ease out, so it decelerates into the value rather than stopping dead.
    const eased = 1 - (1 - through) ** 3;
    element.textContent = `${prefix}${(target * eased).toFixed(decimals)}${suffix}`;
    if (through < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

/* ── sections arriving ───────────────────────────────────────────── */

if (!still) {
  const arriving = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        entry.target.classList.add("is-here");
        for (const number of entry.target.querySelectorAll("[data-count]")) countUp(number);
        arriving.unobserve(entry.target);
      }
    },
    { threshold: 0.08, rootMargin: "0px 0px -8% 0px" },
  );

  for (const block of document.querySelectorAll(".holds > *, .hero > *")) {
    block.classList.add("arrives");
    arriving.observe(block);
  }

  // Children of a group settle in sequence rather than together.
  for (const group of document.querySelectorAll(".figures, .facts, .steps, .cases, .logos, .limits")) {
    [...group.children].forEach((child, index) => {
      child.style.setProperty("--stagger", `${Math.min(index, 5) * 70}ms`);
    });
  }
}
