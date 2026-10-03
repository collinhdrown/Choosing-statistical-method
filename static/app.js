/*
 * app.js — front end for server.py.
 *
 * The page holds no statistical logic. It keeps the raw answers, posts them to /api/state
 * (or /api/chat), and draws whatever view stat_engine.py sends back.
 */
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

let catalog = { families: {}, tests: [] };
let byName = {};
let answers = {};          // raw answers, including facts the advisor heard ahead of their question
let view = null;           // last view from the server
let fromText = new Set();  // answer keys that came from the description
let transcript = [];       // [{role, content}] sent to the advisor
let lastChanged = null;

async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

/* ========== bubble field ========== */
const W = 1000, H = 720;
const wrap = $("svgwrap"), tip = $("tip");
const svg = d3.select(wrap).append("svg").attr("viewBox", `0 0 ${W} ${H}`)
  .attr("role", "img").attr("aria-label", "Tests still in play");
const gRoot = svg.append("g");
const measurer = svg.append("text").attr("visibility", "hidden")
  .style("font-family", "Figtree, system-ui, sans-serif").style("font-weight", 600);
let preview = null;        // Set of names an option under the pointer would keep

const cssVar = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
function colorFor(name) {
  const t = byName[name];
  const base = d3.hsl(cssVar("--f-" + (t ? t.family : "compare")));
  let h = 0; for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) | 0;
  base.l = Math.max(0.18, Math.min(0.62, base.l + ((Math.abs(h) % 7) - 3) * 0.025));
  return base.toString();
}

const widthAt = (s, f) => { measurer.style("font-size", f + "px").text(s); return measurer.node().getComputedTextLength(); };
// Wrap and shrink a label until the whole block fits in the square inscribed in its circle.
function wrapToFit(name, r) {
  const box = r * Math.SQRT2 * 0.88, words = name.split(/\s+/);
  let f = Math.max(r * 0.42, 4), lines = [];
  while (f > 3.5) {
    lines = []; let cur = "";
    for (const w of words) {
      const trial = cur ? cur + " " + w : w;
      if (!cur || widthAt(trial, f) <= box) cur = trial; else { lines.push(cur); cur = w; }
    }
    if (cur) lines.push(cur);
    if (Math.max(...lines.map(l => widthAt(l, f))) <= box && lines.length * f * 1.15 <= box) break;
    f *= 0.92;
  }
  return { f, lines };
}

function drawField(active) {
  const root = d3.pack().size([W, H]).padding(8)(
    d3.hierarchy({ children: active.map(name => ({ name, value: 1 })) }).sum(d => d.value || 0));
  const dur = reduced ? 0 : 700;
  const sel = gRoot.selectAll("g.bubble").data(root.leaves(), d => d.data.name);

  sel.exit().each(function () { d3.select(this).select("text").remove(); })
    .transition().duration(dur * 0.7).ease(d3.easeCubicIn)
    .attr("transform", function () { return d3.select(this).attr("transform") + " scale(0.01)"; })
    .style("opacity", 0).remove();

  const enter = sel.enter().append("g").attr("class", "bubble").attr("transform", d => `translate(${d.x},${d.y})`);
  enter.append("circle").attr("r", 0);
  enter.append("text").attr("text-anchor", "middle");
  enter.on("mousemove", (ev, d) => showTip(ev, d.data.name)).on("mouseleave", () => { tip.hidden = true; });

  const all = enter.merge(sel);
  all.transition().duration(dur).ease(d3.easeCubicOut).attr("transform", d => `translate(${d.x},${d.y})`);
  all.select("circle").attr("fill", d => colorFor(d.data.name))
    .transition().duration(dur).ease(d3.easeCubicOut).attr("r", d => d.r);
  all.each(function (d) {
    const { f, lines } = wrapToFit(d.data.name, d.r), lh = f * 1.15, y0 = -((lines.length - 1) / 2) * lh;
    const tx = d3.select(this).select("text");
    tx.selectAll("tspan").remove();
    lines.forEach((l, i) => tx.append("tspan").attr("x", 0).attr("y", y0 + i * lh).attr("dy", "0.32em").text(l));
    tx.style("font-size", f + "px").style("opacity", 0)
      .transition().delay(dur * 0.4).duration(dur * 0.6).style("opacity", 1);
  });
  applyPreview();
}

function applyPreview() {
  gRoot.selectAll("g.bubble")
    .classed("dim", d => !!preview && !preview.has(d.data.name))
    .classed("lit", d => !!preview && preview.size <= 3 && preview.has(d.data.name));
}

function showTip(ev, name) {
  const t = byName[name] || {};
  tip.innerHTML = `<small>${esc(catalog.families[t.family] || "")}</small><b>${esc(name)}</b>${t.note ? `<span>${esc(t.note)}</span>` : ""}`;
  tip.hidden = false;
  const r = wrap.getBoundingClientRect();
  let x = ev.clientX - r.left + 14;
  const y = ev.clientY - r.top + 14;
  if (x + 260 > r.width) x = Math.max(0, ev.clientX - r.left - 270);
  tip.style.left = x + "px"; tip.style.top = y + "px";
}

/* ========== left column ========== */
function renderPath() {
  $("path").innerHTML = view.path.length ? view.path.map(p =>
    `<button class="ans ${fromText.has(p.key) ? "fromtext" : ""} ${p.key === lastChanged ? "pop" : ""}" data-k="${esc(p.key)}" type="button" title="Undo from here">` +
    `<span class="k">${esc(p.short)}</span><b>${esc(p.label)}</b></button>`).join("")
    : `<span class="empty">Nothing yet. Pick an answer below or describe your study.</span>`;
}

function questionCard(q) {
  return `<div class="card q">
    <div class="head"><span class="label">Question ${q.number}</span><span class="label">${esc(q.short)}</span></div>
    <h2>${esc(q.question)}</h2>
    ${q.hint ? `<p class="hint">${esc(q.hint)}</p>` : ""}
    <div class="opts">${q.options.map((o, i) => {
      const n = o.remaining.length;
      return `<button class="opt ${n ? "" : "dead"}" style="--i:${i}" data-i="${i}" type="button">
        <span class="key">${i + 1}</span><span class="t">${esc(o.label)}</span><span class="n">${n ? `${n} left` : "no match"}</span></button>`;
    }).join("")}</div>
    <div class="qfoot"><span>Hover an answer to preview what it keeps.</span><span><kbd>1</kbd>–<kbd>${q.options.length}</kbd> to answer, <kbd>⌫</kbd> to undo</span></div>
  </div>`;
}

function resultCard(r) {
  const short = k => esc((view.path.find(p => p.key === k) || {}).short || k);
  if (r.status === "complete") {
    return `<div class="card result">
      <div><span class="label">Recommended test</span><h2>${esc(r.test)}</h2></div>
      ${r.note ? `<p>${esc(r.note)}</p>` : ""}
      <p class="sub">Matched on ${view.path.length} answers. Tap an answer chip to change it.</p>
      ${view.what_ifs.length ? `<div class="whatif"><span class="label">If one answer were different</span>${view.what_ifs.map((w, i) =>
        `<button type="button" data-wi="${i}"><span>${esc(w.short)}: ${esc(w.label)}</span><b>${esc(w.test)}</b></button>`).join("")}</div>` : ""}
    </div>`;
  }
  if (r.status === "ambiguous") {
    return `<div class="card result bad"><span class="label">Still tied</span><h2>${r.tests.map(esc).join(" or ")}</h2><p>Add more detail in the description to separate these.</p></div>`;
  }
  return `<div class="card result bad"><span class="label">No test fits</span><h2>These answers conflict</h2><p>Try changing: ${r.conflicts.map(short).join(", ") || "your last answer"}.</p></div>`;
}

function renderTray() {
  const gone = Object.entries(view.eliminated);
  $("traylabel").textContent = `Ruled out (${gone.length})`;
  $("tray").innerHTML = gone.length
    ? gone.reverse().map(([n, by]) => `<span class="gone"><s>${esc(n)}</s><em>${esc(by)}</em></span>`).join("")
    : `<span class="none">Tests you rule out collect here, tagged with the answer that removed them.</span>`;
}

function render() {
  $("count").innerHTML = `${view.active.length}<small> / ${catalog.tests.length}</small>`;
  renderPath();
  $("stage").innerHTML = view.question ? questionCard(view.question) : resultCard(view.result);
  renderTray();
  preview = null;
  drawField(view.active);
}

function renderTranscript() {
  const box = $("transcript");
  box.replaceChildren(...transcript.map(m => {
    const el = document.createElement("div");
    el.className = `msg ${m.role}${m.pending ? " pending" : ""}`;
    el.textContent = m.content;
    return el;
  }));
  box.scrollTop = box.scrollHeight;
}

/* ========== actions ========== */
async function update(next, changedKey) {
  answers = next;
  lastChanged = changedKey;
  try {
    view = await api("/api/state", { answers });
  } catch (err) {
    $("stage").innerHTML = `<div class="card result bad"><span class="label">Something went wrong</span><p>${esc(err.message)}</p></div>`;
    return;
  }
  for (const k of [...fromText]) if (!(k in view.answers)) fromText.delete(k);
  render();
}

function undoFrom(key) {
  const kept = {};
  for (const p of view.path) { if (p.key === key) break; kept[p.key] = view.answers[p.key]; }
  update(kept, null);
}

async function send(message) {
  transcript.push({ role: "user", content: message });
  transcript.push({ role: "assistant", content: "Reading your description…", pending: true });
  renderTranscript();
  $("send").disabled = true;
  try {
    const history = transcript.filter(m => !m.pending && m.role !== "error").slice(0, -1);
    const res = await api("/api/chat", { message, transcript: history, answers });
    transcript.pop();
    transcript.push({ role: "assistant", content: res.reply });
    res.from_text.forEach(k => fromText.add(k));
    answers = res.answers;
    view = res.view;
    lastChanged = null;
    render();
  } catch (err) {
    transcript.pop();
    transcript.push({ role: "error", content: err.message });
  }
  $("send").disabled = false;
  renderTranscript();
}

document.addEventListener("click", e => {
  const o = e.target.closest(".opt");
  if (o) { const q = view.question, opt = q.options[+o.dataset.i]; return update({ ...answers, [q.key]: opt.value }, q.key); }
  const a = e.target.closest(".ans");
  if (a) return undoFrom(a.dataset.k);
  const w = e.target.closest("[data-wi]");
  if (w) { const it = view.what_ifs[+w.dataset.wi]; fromText.clear(); return update(it.answers, null); }
});

document.addEventListener("mouseover", e => {
  const o = e.target.closest(".opt");
  const next = o && view.question ? new Set(view.question.options[+o.dataset.i].remaining) : null;
  const same = (a, b) => a === b || (a && b && a.size === b.size && [...a].every(x => b.has(x)));
  if (!same(next, preview)) { preview = next; applyPreview(); }
});

document.addEventListener("keydown", e => {
  if (e.target.closest("textarea, input")) return;
  if (e.key === "Backspace" && view && view.path.length) { e.preventDefault(); return undoFrom(view.path[view.path.length - 1].key); }
  const n = parseInt(e.key, 10);
  const btn = n ? document.querySelectorAll(".opt")[n - 1] : null;
  if (btn) btn.click();
});

$("chat-form").addEventListener("submit", e => {
  e.preventDefault();
  const text = $("desc").value.trim();
  if (!text || $("send").disabled) return;
  $("desc").value = "";
  send(text);
});
$("desc").addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("chat-form").requestSubmit(); }
});

$("reset").onclick = () => {
  fromText.clear(); transcript = []; renderTranscript();
  update({}, null);
};

$("theme").onclick = () => {
  const root = document.documentElement;
  const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  root.dataset.theme = dark ? "light" : "dark";
  try { localStorage.setItem("theme", root.dataset.theme); } catch (err) {}
  gRoot.selectAll("g.bubble circle").attr("fill", d => colorFor(d.data.name));
};

/* ========== start ========== */
(async function start() {
  catalog = await api("/api/catalog");
  byName = Object.fromEntries(catalog.tests.map(t => [t.name, t]));
  $("legend").innerHTML = Object.entries(catalog.families)
    .map(([k, n]) => `<span><i style="background:var(--f-${esc(k)})"></i>${esc(n)}</span>`).join("");
  await update({}, null);
})();
