// Gemeinsame Helfer: Bild-Stepper und Inhaltsverzeichnis-Markierung.

/**
 * Bild-Stepper: blättert durch die Zwischenbilder einer Pipeline.
 * sets:  [{label, dir}]   - Bildsätze (z. B. verschiedene Testfotos)
 * steps: [{file, title, text, fn, pix}] - file relativ zu dir; pix = Maske (scharf skalieren)
 */
function makeStepper(root, sets, steps) {
  let set = 0, i = 0;
  root.innerHTML = `
    <div class="bar">
      <div class="sets"></div>
      <span class="pill acc">Pfeiltasten ← → zum Blättern</span>
    </div>
    <div class="view">
      <div class="imgbox"><img alt=""></div>
      <div class="txt"><div class="st"></div><h4></h4><p></p><div class="fn"></div></div>
    </div>
    <div class="nav">
      <button class="prev">← Zurück</button>
      <div class="dots"></div>
      <button class="next primary">Weiter →</button>
    </div>`;
  const q = s => root.querySelector(s);
  const img = q("img"), setBox = q(".sets"), dots = q(".dots");
  sets.forEach((s, k) => {
    const b = document.createElement("button");
    b.textContent = s.label;
    b.onclick = () => { set = k; render(); };
    setBox.appendChild(b);
  });
  steps.forEach((_, k) => {
    const d = document.createElement("span");
    d.title = steps[k].title;
    d.onclick = () => { i = k; render(); };
    dots.appendChild(d);
  });
  function render() {
    const s = steps[i];
    img.src = `${sets[set].dir}/${s.file}`;
    img.alt = s.title;
    img.className = s.pix ? "pix" : "";
    q(".st").textContent = `Schritt ${i + 1} / ${steps.length}`;
    q("h4").textContent = s.title;
    q(".txt p").innerHTML = s.text;
    q(".fn").textContent = s.fn || "";
    [...setBox.children].forEach((b, k) => b.classList.toggle("on", k === set));
    [...dots.children].forEach((d, k) => d.classList.toggle("on", k === i));
    q(".prev").disabled = i === 0;
    q(".next").disabled = i === steps.length - 1;
  }
  q(".prev").onclick = () => { if (i > 0) { i--; render(); } };
  q(".next").onclick = () => { if (i < steps.length - 1) { i++; render(); } };
  root.tabIndex = 0;
  root.addEventListener("keydown", e => {
    if (e.key === "ArrowRight") q(".next").click();
    if (e.key === "ArrowLeft") q(".prev").click();
  });
  if (setBox.children.length < 2) setBox.style.visibility = "hidden";
  render();
}

// Aktiven Abschnitt im Inhaltsverzeichnis hervorheben
document.addEventListener("DOMContentLoaded", () => {
  const links = [...document.querySelectorAll("nav.toc li a")];
  const byId = new Map(links.map(a => [a.getAttribute("href").slice(1), a]));
  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        links.forEach(a => a.classList.remove("active"));
        byId.get(e.target.id)?.classList.add("active");
      }
    });
  }, { rootMargin: "-20% 0px -70% 0px" });
  document.querySelectorAll("main section[id]").forEach(s => obs.observe(s));
});

/**
 * Zyklus des Orchestrators (orchestrator/state_machine.py) als SVG; `mod` = "M1" | "M2" | "M3"
 * hebt die Zustände dieses Moduls hervor.
 */
function drawCycle(el, mod) {
  const S = [
    ["DETECT", "M1", "Bauteil erkennen", "ObjectPose"],
    ["PICK", "M2", "Bauteil greifen", ""],
    ["PLACE_INSPECT", "M2", "an Prüfplatz ablegen", ""],
    ["INSPECT", "M3", "Sichtprüfung", "InspectionResult"],
    ["PICK_INSPECT", "M2", "vom Prüfplatz greifen", ""],
    ["SORT", "M2", "sortieren, Home", ""],
  ];
  const w = 165, h = 74, gap = 22, x0 = 70, y0 = 46;
  let s = `<svg viewBox="0 0 ${x0 + S.length * (w + gap) + 10} 200" role="img" aria-label="Zyklus des Orchestrators">
    <defs><marker id="ah${mod}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M0,0 L10,5 L0,10 z" class="f-muted"/></marker></defs>
    <rect x="4" y="${y0 + 18}" width="52" height="38" rx="19" class="f-surface2" stroke="currentColor" stroke-opacity=".25"/>
    <text x="30" y="${y0 + 42}" text-anchor="middle" font-size="12" font-weight="700" class="f-text">IDLE</text>`;
  S.forEach(([name, m, desc, out], k) => {
    const x = x0 + k * (w + gap), on = m === mod;
    s += `<rect x="${x}" y="${y0}" width="${w}" height="${h}" rx="10" class="${on ? "f-accsoft" : "f-surface2"}"
            stroke="${on ? "var(--accent)" : "currentColor"}" stroke-opacity="${on ? 1 : .2}" stroke-width="${on ? 2 : 1}"/>
          <text x="${x + 10}" y="${y0 + 21}" font-size="12" font-family="var(--mono)" font-weight="700" class="${on ? "f-acc" : "f-muted"}">${name}</text>
          <text x="${x + 10}" y="${y0 + 44}" font-size="13" class="f-text">${desc}</text>
          <text x="${x + w - 10}" y="${y0 + h - 9}" font-size="13" text-anchor="end" font-weight="700" class="${on ? "f-acc" : "f-muted"}">${m}${name === "PICK" || name === "PLACE_INSPECT" ? " / M4" : ""}</text>`;
    if (out) s += `<text x="${x + w / 2}" y="${y0 + h + 22}" font-size="13" text-anchor="middle" font-family="var(--mono)" class="f-muted">→ ${out}</text>`;
    const ax = k === 0 ? 58 : x - gap + 2;
    s += `<line x1="${ax}" y1="${y0 + h / 2}" x2="${x - 3}" y2="${y0 + h / 2}" stroke="currentColor" stroke-opacity=".45" marker-end="url(#ah${mod})"/>`;
  });
  const xe = x0 + S.length * (w + gap) - gap;
  s += `<path d="M${xe - w / 2},${y0} V18 H30 V${y0 + 16}" fill="none" stroke="currentColor" stroke-opacity=".35" stroke-dasharray="4 4" marker-end="url(#ah${mod})"/>
        <text x="${(xe + 30) / 2}" y="13" text-anchor="middle" font-size="11" class="f-muted">nächster Zyklus</text>
        <text x="${x0}" y="${y0 + h + 60}" font-size="13" class="f-muted">Jede Ausnahme (VisionError, RobotError, InspectionError) → ERROR: robot.stop(), weiter erst nach „Fehler quittieren“.</text>
        </svg>`;
  el.innerHTML = s;
}

const fmt = (v, d = 1) => Number(v).toLocaleString("de-DE", { minimumFractionDigits: d, maximumFractionDigits: d });
const wrapDeg = a => { a = ((a + 180) % 360 + 360) % 360 - 180; return a === -180 ? 180 : a; };
