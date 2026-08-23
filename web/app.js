// The screen never decides anything. It shows what the pipeline returned, in the
// order the checks ran, and says plainly when it could not reach an answer.

const MARKS = { pass: "✓", fail: "✕", unknown: "?" };
const HEADLINE = { certified: "Certified", flagged: "Flagged", unsigned: "Unsigned" };

const el = (id) => document.getElementById(id);
const exhibit = el("exhibit");
const fileInput = el("file");
const brand = el("brand");
const examine = el("examine");
const findings = el("findings");
const verdict = el("verdict");
const idle = el("idle");
const state = el("state");

let chosen = null;

function show(file) {
  chosen = file;
  examine.disabled = false;
  exhibit.innerHTML = "";
  if (file.type.startsWith("image/")) {
    const img = document.createElement("img");
    img.alt = "The document being examined";
    // Reserve the real box once known, so the column does not jump under the reader.
    img.addEventListener("load", () => {
      img.width = img.naturalWidth;
      img.height = img.naturalHeight;
    }, { once: true });
    img.src = URL.createObjectURL(file);
    exhibit.append(img);
  } else {
    const prompt = document.createElement("span");
    prompt.className = "prompt";
    prompt.textContent = file.name;
    exhibit.append(prompt);
  }
}

exhibit.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => fileInput.files[0] && show(fileInput.files[0]));

for (const name of ["dragenter", "dragover"]) {
  exhibit.addEventListener(name, (event) => {
    event.preventDefault();
    exhibit.classList.add("over");
  });
}
for (const name of ["dragleave", "drop"]) {
  exhibit.addEventListener(name, () => exhibit.classList.remove("over"));
}
exhibit.addEventListener("drop", (event) => {
  event.preventDefault();
  const file = event.dataTransfer.files[0];
  if (file) show(file);
});

function render(decision) {
  verdict.innerHTML = "";
  const stamp = document.createElement("div");
  stamp.className = "stamp";
  stamp.dataset.verdict = decision.verdict;
  stamp.textContent = HEADLINE[decision.verdict] ?? decision.verdict;
  const reason = document.createElement("p");
  reason.className = "reason";
  reason.textContent = decision.reason;
  verdict.append(stamp, reason);

  findings.innerHTML = "";
  findings.hidden = false;
  decision.signals.forEach((signal, index) => {
    const row = document.createElement("li");
    row.className = "finding";
    // The checks genuinely complete in sequence, so they arrive in sequence.
    row.style.animationDelay = `${index * 70}ms`;
    row.innerHTML = `
      <span class="mark" data-outcome="${signal.outcome}" aria-hidden="true"></span>
      <span class="check"></span>
      <span class="detail"></span>
      <span class="provenance"></span>`;
    row.querySelector(".mark").textContent = MARKS[signal.outcome] ?? "?";
    row.querySelector(".check").textContent = signal.name;
    row.querySelector(".detail").textContent = signal.detail;
    row.querySelector(".provenance").textContent = signal.source;
    findings.append(row);
  });
}

function fail(message) {
  verdict.innerHTML = "";
  findings.hidden = true;
  const note = document.createElement("p");
  note.className = "note error";
  note.textContent = message;
  verdict.append(note);
}

examine.addEventListener("click", async () => {
  if (!chosen) return;
  idle.hidden = true;
  examine.disabled = true;
  examine.textContent = "Examining…";

  const body = new FormData();
  body.append("file", chosen);
  if (brand.value.trim()) body.append("brand", brand.value.trim());

  try {
    const response = await fetch("/api/verify", { method: "POST", body });
    const payload = await response.json();
    if (!response.ok) {
      fail(payload.error ?? "That document could not be examined.");
    } else {
      render(payload);
    }
  } catch {
    fail("The examiner is not reachable. Start it and try again.");
  } finally {
    examine.disabled = false;
    examine.textContent = "Examine";
  }
});

fetch("/api/health")
  .then((response) => response.json())
  .then((health) => {
    state.textContent = health.extraction ? "extraction live" : "extraction off";
  })
  .catch(() => {
    state.textContent = "offline";
  });
