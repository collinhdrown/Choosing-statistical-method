/*
 * anova.js — the ANOVA lab tab: a guided walk through the ANOVA family with hopping animals.
 *
 * Everything here runs in the browser: each scene builds a small made-up data set from a fixed
 * seed, runs the matching test on it, and redraws the animals as the controls move. Each animal
 * is one data point and always hops to the same height (its tick mark). Uses $ and esc from
 * app.js. Routes live in the URL hash:
 *   #anova          the scene list
 *   #anova/<slug>   one scene
 */

/* ========== numbers ========== */
function rng(seed) {   // mulberry32
  return () => {
    seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function normals(seed, n) {
  const r = rng(seed), out = [];
  while (out.length < n) {
    const u = 1 - r(), v = r();
    out.push(Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v));
  }
  return out;
}
const sum = a => a.reduce((s, v) => s + v, 0);
const mean = a => sum(a) / a.length;
const ss = (a, m = mean(a)) => sum(a.map(v => (v - m) ** 2));
const sd = a => Math.sqrt(ss(a) / (a.length - 1));
// Rescale to mean 0, SD 1 exactly, so a slider sets the sample's spread, not just the population's.
function standardized(seed, n) {
  const z = normals(seed, n), m = mean(z), s = sd(z);
  return z.map(v => (v - m) / s);
}

function lgamma(x) {
  const c = [76.18009172947146, -86.50532032941677, 24.01409824083091, -1.231739572450155, 0.1208650973866179e-2, -0.5395239384953e-5];
  let y = x, tmp = x + 5.5, ser = 1.000000000190015;
  tmp -= (x + 0.5) * Math.log(tmp);
  for (const ci of c) ser += ci / ++y;
  return -tmp + Math.log(2.5066282746310005 * ser / x);
}
function betacf(a, b, x) {
  let c = 1, d = 1 - (a + b) * x / (a + 1);
  if (Math.abs(d) < 1e-30) d = 1e-30;
  d = 1 / d;
  let h = d;
  for (let m = 1; m <= 200; m++) {
    const m2 = 2 * m;
    let aa = m * (b - m) * x / ((a - 1 + m2) * (a + m2));
    d = 1 + aa * d; if (Math.abs(d) < 1e-30) d = 1e-30;
    c = 1 + aa / c; if (Math.abs(c) < 1e-30) c = 1e-30;
    d = 1 / d; h *= d * c;
    aa = -(a + m) * (a + b + m) * x / ((a + m2) * (a + 1 + m2));
    d = 1 + aa * d; if (Math.abs(d) < 1e-30) d = 1e-30;
    c = 1 + aa / c; if (Math.abs(c) < 1e-30) c = 1e-30;
    d = 1 / d;
    const del = d * c;
    h *= del;
    if (Math.abs(del - 1) < 3e-12) break;
  }
  return h;
}
function ibeta(x, a, b) {   // regularized incomplete beta I_x(a, b)
  if (x <= 0) return 0;
  if (x >= 1) return 1;
  const bt = Math.exp(lgamma(a + b) - lgamma(a) - lgamma(b) + a * Math.log(x) + b * Math.log(1 - x));
  return x < (a + 1) / (a + b + 2) ? bt * betacf(a, b, x) / a : 1 - bt * betacf(b, a, 1 - x) / b;
}
// Upper-tail p value of an F statistic.
function fP(F, d1, d2) {
  if (!isFinite(F)) return 0;
  if (F <= 0) return 1;
  return ibeta(d2 / (d2 + d1 * F), d2 / 2, d1 / 2);
}

function oneWay(groups) {
  const all = groups.flat(), grand = mean(all), N = all.length, k = groups.length;
  const ssb = sum(groups.map(g => g.length * (mean(g) - grand) ** 2));
  const ssw = sum(groups.map(g => ss(g)));
  const df1 = k - 1, df2 = N - k;
  const F = ssw < 1e-9 ? (ssb < 1e-9 ? 0 : Infinity) : (ssb / df1) / (ssw / df2);
  return { F, df1, df2, p: fP(F, df1, df2), eta2: ssb / (ssb + ssw || 1), ssb, ssw, msb: ssb / df1, msw: ssw / df2, grand };
}

// Balanced two-way ANOVA. cells[a][b] holds the values for row level a, column level b.
function twoWay(cells) {
  const A = cells.length, B = cells[0].length, n = cells[0][0].length;
  const all = cells.flat(2), grand = mean(all), N = all.length;
  const cm = cells.map(r => r.map(mean));
  const rowM = cells.map(r => mean(r.flat())), colM = [...Array(B)].map((_, b) => mean(cells.map(r => r[b]).flat()));
  const ssA = B * n * sum(rowM.map(m => (m - grand) ** 2));
  const ssB = A * n * sum(colM.map(m => (m - grand) ** 2));
  let ssAB = 0, ssE = 0;
  cells.forEach((r, a) => r.forEach((c, b) => {
    ssAB += n * (cm[a][b] - rowM[a] - colM[b] + grand) ** 2;
    ssE += ss(c, cm[a][b]);
  }));
  const dfE = N - A * B, msE = ssE / dfE;
  const row = (s, df) => { const F = (s / df) / msE; return { F, df1: df, df2: dfE, p: fP(F, df, dfE) }; };
  return { a: row(ssA, A - 1), b: row(ssB, B - 1), ab: row(ssAB, (A - 1) * (B - 1)), cellMeans: cm };
}

// One-way ANCOVA with one covariate. groups = [[{x, y}, ...], ...]
function ancova(groups) {
  const all = groups.flat(), N = all.length, k = groups.length;
  const xbar = mean(all.map(d => d.x)), ybar = mean(all.map(d => d.y));
  let sxyW = 0, sxxW = 0;
  const gm = groups.map(g => ({ x: mean(g.map(d => d.x)), y: mean(g.map(d => d.y)) }));
  groups.forEach((g, i) => g.forEach(d => { sxyW += (d.x - gm[i].x) * (d.y - gm[i].y); sxxW += (d.x - gm[i].x) ** 2; }));
  const bw = sxyW / sxxW;
  const sseFull = sum(groups.map((g, i) => sum(g.map(d => (d.y - gm[i].y - bw * (d.x - gm[i].x)) ** 2))));
  const sxyT = sum(all.map(d => (d.x - xbar) * (d.y - ybar))), sxxT = sum(all.map(d => (d.x - xbar) ** 2));
  const sseRed = ss(all.map(d => d.y)) - sxyT ** 2 / sxxT;
  const df1 = k - 1, df2 = N - k - 1;
  const F = ((sseRed - sseFull) / df1) / (sseFull / df2);
  return { F, df1, df2, p: fP(F, df1, df2), slope: bw, xbar, groupMeans: gm,
    adjMeans: gm.map(m => m.y - bw * (m.x - xbar)), adjust: d => d.y - bw * (d.x - xbar) };
}

// One-way MANOVA with two outcomes (Pillai's trace). groups = [[[y1, y2], ...], ...]
function manova2(groups) {
  const all = groups.flat(), N = all.length, k = groups.length, p = 2;
  const cross = (pts, m) => {
    let a = 0, b = 0, c = 0;
    for (const [u, v] of pts) { a += (u - m[0]) ** 2; b += (u - m[0]) * (v - m[1]); c += (v - m[1]) ** 2; }
    return [a, b, c];
  };
  const m2 = pts => [mean(pts.map(d => d[0])), mean(pts.map(d => d[1]))];
  const T = cross(all, m2(all));
  const E = groups.map(g => cross(g, m2(g))).reduce((s, x) => s.map((v, i) => v + x[i]));
  const H = T.map((v, i) => v - E[i]);
  const det = T[0] * T[2] - T[1] ** 2;
  const Ti = [T[2] / det, -T[1] / det, T[0] / det];
  const V = H[0] * Ti[0] + 2 * H[1] * Ti[1] + H[2] * Ti[2];   // trace(H T^-1)
  const s = Math.min(p, k - 1), m = (Math.abs(p - (k - 1)) - 1) / 2, n = (N - k - p - 1) / 2;
  const df1 = s * (2 * m + s + 1), df2 = s * (2 * n + s + 1);
  const F = ((2 * n + s + 1) / (2 * m + s + 1)) * (V / (s - V));
  return { V, F, df1, df2, p: fP(F, df1, df2) };
}

const fmtF = F => !isFinite(F) ? "∞" : F >= 100 ? F.toFixed(0) : F.toFixed(2);
const fmtP = p => p < 0.001 ? "< .001" : p.toFixed(3).replace(/^0/, "");
const pct = x => `${Math.round(x * 100)}%`;
const verdict = p => p < 0.05
  ? `<span class="verdict yes">Good evidence of a real difference</span>`
  : `<span class="verdict no">Could easily be chance</span>`;

/* ========== animals ========== */
const COLORS = [
  { key: "green", name: "Green", hex: "#3E9B54" },
  { key: "blue", name: "Blue", hex: "#3B7DD8" },
  { key: "yellow", name: "Yellow", hex: "#E0A526" },
];
const PLAIN = "#7C8A6E";

// Each shape stands on y = 0 and is about 24 units wide.
const SHAPES = {
  frog: c => `<ellipse cx="-10" cy="-3" rx="5" ry="3" fill="${c}"/><ellipse cx="10" cy="-3" rx="5" ry="3" fill="${c}"/>
    <ellipse cx="0" cy="-9" rx="11" ry="7.5" fill="${c}"/>
    <circle cx="-5.5" cy="-16" r="3.6" fill="${c}"/><circle cx="5.5" cy="-16" r="3.6" fill="${c}"/>
    <circle cx="-5.5" cy="-16.5" r="1.8" fill="#fff"/><circle cx="5.5" cy="-16.5" r="1.8" fill="#fff"/>
    <circle cx="-5.2" cy="-16.5" r="0.9" fill="#1D231E"/><circle cx="5.8" cy="-16.5" r="0.9" fill="#1D231E"/>`,
  rabbit: c => `<ellipse cx="-3.5" cy="-27" rx="2.2" ry="6.5" fill="${c}"/><ellipse cx="3.5" cy="-27" rx="2.2" ry="6.5" fill="${c}"/>
    <ellipse cx="0" cy="-8" rx="9" ry="8" fill="${c}"/><circle cx="0" cy="-19" r="6" fill="${c}"/>
    <circle cx="-8.5" cy="-6" r="2.6" fill="#fff" opacity=".85"/>
    <circle cx="2.3" cy="-20" r="1.1" fill="#1D231E"/>`,
  grasshopper: c => `<path d="M-3,-8 L-9,-17 L-15,-1" fill="none" stroke="${c}" stroke-width="2.4" stroke-linejoin="round"/>
    <ellipse cx="0" cy="-6" rx="12" ry="4" fill="${c}"/><circle cx="12" cy="-8" r="4" fill="${c}"/>
    <path d="M13,-11 Q16,-20 22,-21" fill="none" stroke="${c}" stroke-width="1.2"/>
    <path d="M4,-3 L6,0 M-2,-3 L-3,0" stroke="${c}" stroke-width="1.6"/>
    <circle cx="13.3" cy="-8.8" r="1" fill="#1D231E"/>`,
};

/* ========== hopping stage ========== */
// A stage draws animals on a shared height axis. Animals ease to new heights, so dragging a slider
// moves each one smoothly instead of reshuffling the scene.
const stages = new Set();
let hopFrame = 0;

function makeStage(el, { w = 760, h = 300, ymax = 100, unit = "cm", label = "Hop height" } = {}) {
  const top = 18, ground = h - 36, left = 50, right = w - 96;
  const py = v => ground - (Math.max(0, v) / ymax) * (ground - top);
  const px = f => left + f * (right - left);
  const ticks = [...Array(5)].map((_, i) => (ymax / 4) * i);
  el.innerHTML = `<svg class="stage" viewBox="0 0 ${w} ${h}" role="img" aria-label="Animals hopping; each tick marks one animal's hop height">
    <g class="axis">${ticks.map(t => `<line x1="${left}" x2="${right}" y1="${py(t)}" y2="${py(t)}"/>
      <text x="${left - 8}" y="${py(t) + 4}" text-anchor="end">${t}</text>`).join("")}
      <text class="ylab" transform="translate(13 ${(top + ground) / 2}) rotate(-90)" text-anchor="middle">${esc(label)} (${unit})</text></g>
    <line class="ground" x1="${left}" x2="${right}" y1="${ground}" y2="${ground}"/>
    <g class="marks"></g><g class="lines"></g><g class="animals"></g><g class="glabels"></g></svg>`;
  const svgEl = el.querySelector("svg");
  const g = n => svgEl.querySelector(`.${n}`);
  const st = { el, animals: new Map(), lines: new Map(), py, unit };

  st.set = list => {
    const seen = new Set();
    list.forEach(a => {
      seen.add(a.id);
      let s = st.animals.get(a.id);
      if (!s) {
        const node = document.createElementNS("http://www.w3.org/2000/svg", "g");
        const mark = document.createElementNS("http://www.w3.org/2000/svg", "line");
        g("animals").appendChild(node); g("marks").appendChild(mark);
        s = { node, mark, cur: a.value };
        st.animals.set(a.id, s);
      }
      if (s.shape !== a.shape + a.color) { s.node.innerHTML = SHAPES[a.shape](a.color); s.shape = a.shape + a.color; }
      Object.assign(s, { x: px(a.x), target: a.value, size: a.size || 1, period: a.period || 2.2 });
      s.mark.setAttribute("stroke", a.color);
      if (reduced) s.cur = a.value;
    });
    for (const [id, s] of st.animals) if (!seen.has(id)) { s.node.remove(); s.mark.remove(); st.animals.delete(id); }
    st.draw(performance.now());
  };

  // lines: [{id, x0, x1, value, color, label, overall}]
  st.lines = list => {
    g("lines").innerHTML = list.map(l => {
      const y = py(l.value);
      return `<g class="mline ${l.overall ? "overall" : ""}">
        <line x1="${px(l.x0)}" x2="${px(l.x1)}" y1="${y}" y2="${y}" stroke="${l.color}"/>
        ${l.label ? `<text x="${px(l.x1) + 6}" y="${y + 4}" fill="${l.color}">${esc(l.label)}</text>` : ""}</g>`;
    }).join("");
  };
  // labels under the ground: [{x, text, color}]
  st.labels = list => {
    g("glabels").innerHTML = list.map(l =>
      `<text x="${px(l.x)}" y="${ground + 22}" text-anchor="middle" fill="${l.color || "currentColor"}">${esc(l.text)}</text>`).join("");
  };

  st.draw = now => {
    const t = now / 1000;
    for (const s of st.animals.values()) {
      if (!reduced) s.cur += (s.target - s.cur) * 0.14;
      const peak = ground - py(s.cur);
      // Every animal takes off together and hangs briefly at the top, so the heights line up for comparison.
      const lift = reduced ? 1 : Math.min(1, 1.25 * Math.sin(Math.PI * ((t / s.period) % 1)));
      s.node.setAttribute("transform", `translate(${s.x} ${ground - peak * lift}) scale(${s.size})`);
      const y = py(s.cur);
      s.mark.setAttribute("x1", s.x - 9); s.mark.setAttribute("x2", s.x + 9);
      s.mark.setAttribute("y1", y); s.mark.setAttribute("y2", y);
    }
  };
  stages.add(st);
  startHops();
  return st;
}

function startHops() {
  if (reduced || hopFrame) return;
  const tick = now => {
    if ($("view-anova").hidden || !stages.size) { hopFrame = 0; return; }
    for (const st of stages) st.draw(now);
    hopFrame = requestAnimationFrame(tick);
  };
  hopFrame = requestAnimationFrame(tick);
}

// Spread n groups across the stage with a gap between them. Returns x positions (0..1) per group.
function groupSlots(sizes, gap = 1.6) {
  const slots = sum(sizes) + gap * (sizes.length - 1);
  let at = 0;
  return sizes.map(n => {
    const xs = [...Array(n)].map((_, i) => (at + i + 0.5) / slots);
    at += n + gap;
    return xs;
  });
}

/* ========== small charts ========== */
function scatter(el, { pts, xdom, ydom, xlab, ylab, lines = [], ellipses = [], xn = 4, yn = 4, w = 360, h = 280 }) {
  const L = 46, R = w - 12, T = 12, B = h - 40;
  const sx = v => L + ((v - xdom[0]) / (xdom[1] - xdom[0])) * (R - L);
  const sy = v => B - ((v - ydom[0]) / (ydom[1] - ydom[0])) * (B - T);
  const tk = (d, n = 4) => [...Array(n + 1)].map((_, i) => d[0] + ((d[1] - d[0]) / n) * i);
  el.innerHTML = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(ylab)} against ${esc(xlab)}">
    <defs><clipPath id="clip-${el.id}"><rect x="${L}" y="${T}" width="${R - L}" height="${B - T}"/></clipPath></defs>
    <g class="axis">${tk(ydom, yn).map(v => `<line x1="${L}" x2="${R}" y1="${sy(v)}" y2="${sy(v)}"/><text x="${L - 6}" y="${sy(v) + 4}" text-anchor="end">${+v.toFixed(1)}</text>`).join("")}
    ${tk(xdom, xn).map(v => `<text x="${sx(v)}" y="${B + 16}" text-anchor="middle">${+v.toFixed(1)}</text>`).join("")}
    <text x="${(L + R) / 2}" y="${h - 4}" text-anchor="middle" class="ylab">${esc(xlab)}</text>
    <text transform="translate(12 ${(T + B) / 2}) rotate(-90)" text-anchor="middle" class="ylab">${esc(ylab)}</text></g>
    <g clip-path="url(#clip-${el.id})">
    ${ellipses.map(e => `<path d="${e.pts.map((p, i) => `${i ? "L" : "M"}${sx(p[0]).toFixed(1)},${sy(p[1]).toFixed(1)}`).join("")}Z" fill="${e.color}" fill-opacity=".14" stroke="${e.color}" stroke-opacity=".6"/>`).join("")}
    ${lines.map(l => `<line x1="${sx(l.x0)}" x2="${sx(l.x1)}" y1="${sy(l.y0)}" y2="${sy(l.y1)}" stroke="${l.color}" stroke-width="2" ${l.dash ? 'stroke-dasharray="5 4"' : ""}/>`).join("")}
    ${pts.map(p => `<circle cx="${sx(p.x)}" cy="${sy(p.y)}" r="4.2" fill="${p.color}" stroke="var(--panel)" stroke-width="1"/>`).join("")}
    </g></svg>`;
}

function interactionPlot(el, cellMeans, species) {
  const w = 380, h = 260, L = 46, R = w - 112, T = 14, B = h - 40;
  const all = cellMeans.flat(), lo = Math.min(20, ...all) - 5, hi = Math.max(80, ...all) + 5;
  const sx = j => L + (j / 2) * (R - L), sy = v => B - ((v - lo) / (hi - lo)) * (B - T);
  const DASH = ["", "6 4", "2 3"];
  el.innerHTML = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Mean hop height by color, one line per species">
    <g class="axis">${[0, 1, 2].map(j => `<text x="${sx(j)}" y="${B + 18}" text-anchor="middle" fill="${COLORS[j].hex}">${COLORS[j].name}</text>`).join("")}
    ${[0, 0.5, 1].map(f => lo + f * (hi - lo)).map(v => `<line x1="${L}" x2="${R}" y1="${sy(v)}" y2="${sy(v)}"/><text x="${L - 6}" y="${sy(v) + 4}" text-anchor="end">${v.toFixed(0)}</text>`).join("")}
    <text transform="translate(12 ${(T + B) / 2}) rotate(-90)" text-anchor="middle" class="ylab">Mean hop (cm)</text></g>
    ${cellMeans.map((r, i) => `<polyline points="${r.map((v, j) => `${sx(j)},${sy(v)}`).join(" ")}" fill="none" stroke="var(--ink)" stroke-width="2" stroke-dasharray="${DASH[i]}"/>
      ${r.map((v, j) => `<circle cx="${sx(j)}" cy="${sy(v)}" r="4" fill="${COLORS[j].hex}"/>`).join("")}
      <text x="${R + 8}" y="${sy(r[2]) + 4}" class="slab">${species[i]}</text>`).join("")}
  </svg>`;
}

/* ========== page bits ========== */
const slider = (id, label, min, max, step, value, fmt = "") =>
  `<label class="ctl" for="${id}"><span class="ctl-l">${label}</span>
    <input type="range" id="${id}" min="${min}" max="${max}" step="${step}" value="${value}">
    <output id="${id}-out" for="${id}">${fmt}</output></label>`;
const toggle = (id, label, on) =>
  `<button type="button" class="switch" id="${id}" role="switch" aria-checked="${on}"><span class="knob" aria-hidden="true"></span>${label}</button>`;
const readout = items => items.map(([k, v]) => `<div class="ro"><span class="k">${k}</span><span class="v">${v}</span></div>`).join("");
const onInput = (el, id, fn) => el.querySelector("#" + id).addEventListener("input", fn);
const onSwitch = (el, id, fn) => el.querySelector("#" + id).addEventListener("click", e => {
  const b = e.currentTarget, on = b.getAttribute("aria-checked") !== "true";
  b.setAttribute("aria-checked", on); fn();
});
const isOn = (el, id) => el.querySelector("#" + id).getAttribute("aria-checked") === "true";
const val = (el, id) => +el.querySelector("#" + id).value;
const out = (el, id, text) => { el.querySelector(`#${id}-out`).textContent = text; };

/* ========== scenes ========== */
const SCENES = [
  {
    slug: "variance", title: "What is variance?", blurb: "One group of frogs and a slider for how spread out their hops are.",
    intro: [
      "ANOVA tells us how much of the variation in an outcome can be explained by a predictor. By variation, we mean how spread out the values are around the mean.",
      "Here our outcome is how high each frog hops. Each frog always hops to the same height, marked by its tick, so each frog is one data point. The dashed line is the mean.",
    ],
    controls: () => slider("s1-sd", "Spread", 0, 20, 0.5, 8, ""),
    after: "Some frogs hop higher than others, and we want to know why. If we can measure something about each frog, like its color, we can ask whether it explains part of that spread.",
    takeaway: "Variance is how spread out the hops are around the average, not how high the average is.",
    mount(el) {
      const n = 5, z = standardized(11, n), xs = groupSlots([n])[0];
      const st = makeStage(el.querySelector(".stagewrap"));
      const draw = () => {
        const s = val(el, "s1-sd"), ys = z.map(v => 50 + s * v);
        out(el, "s1-sd", `SD ${s.toFixed(1)} cm`);
        st.set(ys.map((y, i) => ({ id: i, x: xs[i], value: y, shape: "frog", color: PLAIN })));
        st.lines([{ x0: 0, x1: 1, value: 50, color: "var(--ink)", label: "mean 50", overall: true }]);
        el.querySelector(".readout").innerHTML = readout([["Mean", "50.0 cm"], ["Standard deviation", `${s.toFixed(1)} cm`], ["Variance", `${(s * s).toFixed(1)} cm²`]]);
      };
      onInput(el, "s1-sd", draw); draw();
    },
  },
  {
    slug: "one-way", title: "One-way ANOVA: does color matter?", blurb: "Three colors of frog and a slider for how much of the variation color explains.",
    intro: [
      "ANOVA is used when the predictor is categorical, meaning it sorts subjects into groups. It works with two or more groups; with exactly two it gives the same answer as a t-test, so ANOVA is usually used for three or more. Our predictor is color, with three levels: green, blue and yellow.",
      "ANOVA tells us whether there's good evidence that color explains some of the variation in the frogs' jumping height (the F test), and what percentage of the total variation color explains in our sample (eta squared).",
    ],
    controls: () => slider("s2-eta", "Variation explained by color", 0, 100, 1, 40, ""),
    takeaway: "ANOVA compares group means, and eta squared is the share of the total variation those mean differences account for.",
    mount(el) {
      const n = 5, k = 3, N = n * k, S = 12, d = [-1, 0.2, 0.8];
      const z = [0, 1, 2].map(g => standardized(21 + g, n)), slots = groupSlots([n, n, n]);
      const st = makeStage(el.querySelector(".stagewrap"));
      st.labels(COLORS.map((c, g) => ({ x: mean(slots[g]), text: c.name, color: c.hex })));
      const draw = () => {
        const eta = val(el, "s2-eta") / 100, T = S * S * (N - 1);
        const a = Math.sqrt((eta * T) / (n * sum(d.map(v => v * v)))), w = Math.sqrt(((1 - eta) * T) / (N - k));
        const groups = z.map((zs, g) => zs.map(v => 50 + a * d[g] + w * v));
        const r = oneWay(groups);
        out(el, "s2-eta", pct(eta));
        st.set(groups.flatMap((ys, g) => ys.map((y, i) => ({ id: `${g}-${i}`, x: slots[g][i], value: y, shape: "frog", color: COLORS[g].hex }))));
        st.lines([{ x0: 0, x1: 1, value: 50, color: "var(--muted)", label: "overall", overall: true },
          ...groups.map((ys, g) => ({ x0: slots[g][0] - 0.03, x1: slots[g][n - 1] + 0.03, value: mean(ys), color: COLORS[g].hex }))]);
        el.querySelector(".readout").innerHTML = readout([["Eta squared", pct(r.eta2)], ["F", fmtF(r.F)], ["p", fmtP(r.p)]]) +
          `<div class="split" aria-label="Total variation split into color and leftover">
            <span class="between" style="width:${r.eta2 * 100}%"></span><span class="within" style="width:${(1 - r.eta2) * 100}%"></span></div>
           <div class="splitkey"><span><i class="between"></i>Explained by color</span><span><i class="within"></i>Left over within each color</span></div>`;
        el.querySelector(".live").textContent = eta >= 0.995
          ? "At 100%, every frog of the same color hops exactly the same height. Knowing a frog's color tells you exactly how high it hops."
          : eta <= 0.005
            ? "At 0%, the three color means sit on the overall mean. Color tells you nothing about how high a frog hops."
            : `Color explains ${pct(eta)} of the variation. The other ${pct(1 - eta)} is spread among frogs of the same color. In real data we never reach 100%: countless other things affect hopping, and whatever color doesn't explain is left over as variation within each color.`;
      };
      onInput(el, "s2-eta", draw); draw();
    },
  },
  {
    slug: "signal-noise", title: "Signal vs noise: the F ratio", blurb: "The color means stay put while the spread inside each color grows.",
    intro: [
      "Sample means always differ a little, even when color has no real effect. So the question is whether the gap between the color means is bigger than random noise would produce. That depends on how spread out the frogs are inside each color.",
      "ANOVA answers it with one ratio. If color doesn't matter, the top and bottom measure the same noise and F lands near 1. If color matters, the top grows and F gets large.",
    ],
    formula: String.raw`F = \frac{\text{spread between group means}}{\text{spread within groups}}`,
    controls: () => slider("s3-sd", "Spread within each color", 1, 25, 0.5, 4, ""),
    after: "The means were identical the whole time. Only the noise changed, and it changed the conclusion. That is why it's called analysis of variance even though the question is about means. With three groups there is no single difference to test, and running three t-tests would raise the chance of a false positive; F covers all the groups in one test.",
    takeaway: "A difference in means only counts when it stands out from the spread inside the groups.",
    mount(el) {
      const n = 5, M = [50, 55, 60];
      const z = [0, 1, 2].map(g => standardized(31 + g, n)), slots = groupSlots([n, n, n]);
      const st = makeStage(el.querySelector(".stagewrap"));
      st.labels(COLORS.map((c, g) => ({ x: mean(slots[g]), text: c.name, color: c.hex })));
      st.lines(M.map((m, g) => ({ x0: slots[g][0] - 0.03, x1: slots[g][n - 1] + 0.03, value: m, color: COLORS[g].hex })));
      const draw = () => {
        const s = val(el, "s3-sd"), groups = z.map((zs, g) => zs.map(v => M[g] + s * v)), r = oneWay(groups);
        out(el, "s3-sd", `SD ${s.toFixed(1)} cm`);
        st.set(groups.flatMap((ys, g) => ys.map((y, i) => ({ id: `${g}-${i}`, x: slots[g][i], value: y, shape: "frog", color: COLORS[g].hex }))));
        el.querySelector(".readout").innerHTML = readout([["Color means", "50, 55, 60 cm"], ["Between", r.msb.toFixed(1)], ["Within", r.msw.toFixed(1)], ["F", fmtF(r.F)], ["p", fmtP(r.p)]]) + verdict(r.p);
      };
      onInput(el, "s3-sd", draw); draw();
    },
  },
  {
    slug: "two-way", title: "Two-way ANOVA: species and color", blurb: "Frogs, rabbits and grasshoppers in three colors, with switches for each effect.",
    intro: [
      "In real studies we often have several predictors and want to look at them together. When two predictors are both categorical, we can use a two-way ANOVA, a type of factorial ANOVA. We've added rabbits and grasshoppers, so we now have two predictors with three levels each: species and color. That makes 9 groups.",
      "A two-way ANOVA asks three questions. Main effect of species: do the species differ in average hop height? Main effect of color: do the colors differ, averaging over species? Interaction: does the effect of color depend on which species you look at?",
    ],
    controls: () => `<div class="switches">${toggle("s4-sp", "Species effect", true)}${toggle("s4-co", "Color effect", false)}${toggle("s4-ix", "Interaction", false)}</div>`,
    extra: `<div class="card chartcard"><span class="label">Interaction plot</span><div id="s4-plot"></div>
      <p class="note">Parallel lines mean no interaction. Lines that cross or fan out mean the effect of color depends on species.</p></div>`,
    after: "With the interaction on, blue frogs hop highest of the frogs, but blue rabbits hop lowest of the rabbits. You can't say what blue does without saying which species. Note that an interaction is not the same as species and color being related (say, most grasshoppers being green); that would be the predictors being correlated, which is a different issue.",
    takeaway: "Main effects are about each predictor on its own; an interaction means one predictor's effect changes depending on the other.",
    mount(el) {
      const n = 2, SP = ["frog", "rabbit", "grasshopper"], SPN = ["Frogs", "Rabbits", "Grasshoppers"];
      const spEff = [0, 14, -14], coEff = [-7, 2, 5], ix = [[-5, 10, -5], [5, -10, 5], [0, 0, 0]];
      const z = SP.map((_, a) => [0, 1, 2].map(b => standardized(41 + a * 3 + b, n)));
      // Species sit apart; within a species the three colors stand side by side.
      const slots = groupSlots([3 * n, 3 * n, 3 * n], 2).flatMap(xs => [0, 1, 2].map(b => xs.slice(b * n, (b + 1) * n)));
      const st = makeStage(el.querySelector(".stagewrap"), { h: 320 });
      st.labels(SPN.map((t, a) => ({ x: mean(slots[a * 3 + 1]), text: t })));
      const draw = () => {
        const on = id => isOn(el, id) ? 1 : 0;
        const cells = SP.map((_, a) => [0, 1, 2].map(b => z[a][b].map(v =>
          50 + on("s4-sp") * spEff[a] + on("s4-co") * coEff[b] + on("s4-ix") * ix[a][b] + 5 * v)));
        const r = twoWay(cells);
        st.set(cells.flatMap((row, a) => row.flatMap((ys, b) => ys.map((y, i) => ({
          id: `${a}-${b}-${i}`, x: slots[a * 3 + b][i], value: y, shape: SP[a], color: COLORS[b].hex, period: 2.2 })))));
        st.lines(cells.flatMap((row, a) => row.map((ys, b) => {
          const s = slots[a * 3 + b];
          return { x0: s[0] - 0.02, x1: s[n - 1] + 0.02, value: mean(ys), color: COLORS[b].hex };
        })));
        interactionPlot(el.querySelector("#s4-plot"), r.cellMeans, SPN);
        const row = (name, x) => `<tr><th>${name}</th><td>${fmtF(x.F)}</td><td>${fmtP(x.p)}</td><td>${verdict(x.p)}</td></tr>`;
        el.querySelector(".readout").innerHTML = `<table class="atable"><thead><tr><th>Effect</th><th>F</th><th>p</th><th></th></tr></thead><tbody>
          ${row("Species", r.a)}${row("Color", r.b)}${row("Species × color", r.ab)}</tbody></table>`;
      };
      for (const id of ["s4-sp", "s4-co", "s4-ix"]) onSwitch(el, id, draw);
      draw();
    },
  },
  {
    slug: "ancova", title: "ANCOVA: accounting for body size", blurb: "Bigger frogs hop higher. Does color still matter once size is accounted for?",
    intro: [
      "Back to frogs only. Bigger frogs tend to hop higher, and body size is a continuous measure, not a group. ANCOVA lets us test whether color still matters after accounting for body size. The continuous variable we account for is called a covariate.",
      "In this sample, the yellow frogs look like the best jumpers, but they also happen to be the biggest.",
    ],
    controls: () => `<div class="switches">${toggle("s5-adj", "Account for body size", false)}</div>`,
    extra: `<div class="card chartcard"><span class="label">Body size vs hop height</span><div id="s5-plot"></div>
      <p class="note">One line per color, all with the same slope. ANCOVA compares the colors where the lines cross the dashed average body size.</p></div>`,
    after: "When you account for body size, each frog's hop is adjusted to what it would be at the average body size, and the color difference disappears. ANCOVA assumes the lines for each color are roughly parallel, meaning body size affects hopping the same way for every color.",
    takeaway: "ANCOVA compares group means as if every group had the same value of the covariate.",
    mount(el) {
      const n = 5, SIZE = [5, 6, 8], coEff = [0, 1, 1.5];
      const groups = [0, 1, 2].map(g => {
        const zx = standardized(51 + g, n), zy = standardized(61 + g, n);
        return zx.map((v, i) => { const x = SIZE[g] + 0.6 * v; return { x, y: 8 + 6 * x + coEff[g] + 3 * zy[i] }; });
      });
      const a = ancova(groups), before = oneWay(groups.map(g => g.map(d => d.y)));
      const slots = groupSlots([n, n, n]);
      const st = makeStage(el.querySelector(".stagewrap"), { ymax: 80 });
      st.labels(COLORS.map((c, g) => ({ x: mean(slots[g]), text: c.name, color: c.hex })));
      const xdom = [4, 10], ydom = [20, 80];
      scatter(el.querySelector("#s5-plot"), {
        pts: groups.flatMap((g, i) => g.map(d => ({ ...d, color: COLORS[i].hex }))), xdom, ydom,
        xlab: "Body size (cm)", ylab: "Hop height (cm)", xn: 6, yn: 6,
        lines: [...a.groupMeans.map((m, i) => ({ x0: xdom[0], x1: xdom[1], y0: m.y + a.slope * (xdom[0] - m.x), y1: m.y + a.slope * (xdom[1] - m.x), color: COLORS[i].hex })),
          { x0: a.xbar, x1: a.xbar, y0: ydom[0], y1: ydom[1], color: "var(--muted)", dash: true }],
      });
      const draw = () => {
        const adj = isOn(el, "s5-adj");
        st.set(groups.flatMap((g, gi) => g.map((d, i) => ({ id: `${gi}-${i}`, x: slots[gi][i], value: adj ? a.adjust(d) : d.y,
          shape: "frog", color: COLORS[gi].hex, size: 0.2 * d.x - 0.15 }))));
        st.lines(groups.map((g, gi) => ({ x0: slots[gi][0] - 0.03, x1: slots[gi][n - 1] + 0.03,
          value: adj ? a.adjMeans[gi] : a.groupMeans[gi].y, color: COLORS[gi].hex })));
        el.querySelector(".readout").innerHTML = `<table class="atable"><thead><tr><th>Color effect</th><th>F</th><th>p</th><th></th></tr></thead><tbody>
          <tr class="${adj ? "dim" : ""}"><th>Ignoring body size</th><td>${fmtF(before.F)}</td><td>${fmtP(before.p)}</td><td>${verdict(before.p)}</td></tr>
          <tr class="${adj ? "" : "dim"}"><th>After accounting for it</th><td>${fmtF(a.F)}</td><td>${fmtP(a.p)}</td><td>${verdict(a.p)}</td></tr></tbody></table>`;
      };
      onSwitch(el, "s5-adj", draw); draw();
    },
  },
  {
    slug: "manova", title: "MANOVA: height and frequency together", blurb: "Two outcomes per frog, tested together instead of one at a time.",
    intro: [
      "Sometimes we care about more than one outcome at once. Here we measure two things for each frog: how high it jumps and how many times it jumps per minute. MANOVA tests whether color affects the two outcomes taken together.",
      "Watch the frogs: they now hop at different speeds as well as different heights.",
    ],
    controls: () => slider("s6-r", "How related height and frequency are", 0, 0.9, 0.05, 0.8, "") + slider("s6-c", "Color effect", 0, 1, 0.05, 0.6, ""),
    extra: `<div class="card chartcard"><span class="label">Frequency vs height</span><div id="s6-plot"></div>
      <p class="note">Each shaded ellipse holds most of one color's frogs.</p></div>`,
    after: "Here the colors overlap a lot on height alone and on frequency alone, so the two separate ANOVAs struggle. But on the scatter plot the groups separate clearly, because yellow frogs jump higher than you'd expect for how often they jump. MANOVA picks that up. Lower the relationship slider and the advantage shrinks.",
    takeaway: "MANOVA is for several related outcomes measured on the same subjects, tested together in one go.",
    mount(el) {
      const n = 5, SH = 8, SF = 6, slots = groupSlots([n, n, n]), dir = [-1, 0, 1];
      const z = [0, 1, 2].map(g => [standardized(171 + g, n), standardized(181 + g, n)]);
      const st = makeStage(el.querySelector(".stagewrap"));
      st.labels(COLORS.map((c, g) => ({ x: mean(slots[g]), text: c.name, color: c.hex })));
      const draw = () => {
        const r = val(el, "s6-r"), c = val(el, "s6-c");
        out(el, "s6-r", r.toFixed(2)); out(el, "s6-c", pct(c));
        const groups = z.map(([z1, z2], g) => z1.map((u, i) => {
          const v = r * u + Math.sqrt(1 - r * r) * z2[i];
          return [50 + SH * (u + c * dir[g]), 40 + SF * (v - c * dir[g])];
        }));
        const m = manova2(groups), aH = oneWay(groups.map(g => g.map(d => d[0]))), aF = oneWay(groups.map(g => g.map(d => d[1])));
        st.set(groups.flatMap((g, gi) => g.map((d, i) => ({ id: `${gi}-${i}`, x: slots[gi][i], value: d[0],
          shape: "frog", color: COLORS[gi].hex, period: 90 / Math.max(15, d[1]) }))));
        st.lines(groups.map((g, gi) => ({ x0: slots[gi][0] - 0.03, x1: slots[gi][n - 1] + 0.03, value: mean(g.map(d => d[0])), color: COLORS[gi].hex })));
        const ell = (pts, color) => {
          const mx = mean(pts.map(d => d[1])), my = mean(pts.map(d => d[0]));
          const a = ss(pts.map(d => d[1])) / (pts.length - 1), cc = ss(pts.map(d => d[0])) / (pts.length - 1);
          const b = sum(pts.map(d => (d[1] - mx) * (d[0] - my))) / (pts.length - 1);
          const l11 = Math.sqrt(a), l21 = b / l11, l22 = Math.sqrt(Math.max(cc - l21 * l21, 1e-9)), k = Math.sqrt(5.991);
          return { color, pts: [...Array(48)].map((_, i) => { const t = (i / 48) * 2 * Math.PI, u = Math.cos(t) * k, v = Math.sin(t) * k; return [mx + l11 * u, my + l21 * u + l22 * v]; }) };
        };
        scatter(el.querySelector("#s6-plot"), {
          pts: groups.flatMap((g, gi) => g.map(d => ({ x: d[1], y: d[0], color: COLORS[gi].hex }))),
          xdom: [10, 70], ydom: [20, 80], xn: 6, yn: 6, xlab: "Jumps per minute", ylab: "Hop height (cm)",
          ellipses: groups.map((g, gi) => ell(g, COLORS[gi].hex)),
        });
        el.querySelector(".readout").innerHTML = `<table class="atable"><thead><tr><th>Test</th><th>F</th><th>p</th><th></th></tr></thead><tbody>
          <tr><th>MANOVA (both together)</th><td>${fmtF(m.F)}</td><td>${fmtP(m.p)}</td><td>${verdict(m.p)}</td></tr>
          <tr class="dim"><th>ANOVA on height alone</th><td>${fmtF(aH.F)}</td><td>${fmtP(aH.p)}</td><td>${verdict(aH.p)}</td></tr>
          <tr class="dim"><th>ANOVA on frequency alone</th><td>${fmtF(aF.F)}</td><td>${fmtP(aF.p)}</td><td>${verdict(aF.p)}</td></tr></tbody></table>
          <p class="note">MANOVA result uses Pillai's trace (V = ${m.V.toFixed(2)}).</p>`;
      };
      onInput(el, "s6-r", draw); onInput(el, "s6-c", draw); draw();
    },
  },
];

/* ========== pages ========== */
function anovaListPage() {
  return `<div class="xintro"><h2>ANOVA lab</h2>
      <p>A guided walk through the ANOVA family with hopping animals. Each scene has one thing to play with; move the controls and watch the test result change.</p></div>
    <ol class="quizgrid scenegrid">${SCENES.map((s, i) => `
      <li><a class="card quizcard" href="#anova/${s.slug}">
        <span class="label">Scene ${i + 1}</span>
        <h3>${esc(s.title)}</h3>
        <p>${esc(s.blurb)}</p>
      </a></li>`).join("")}</ol>`;
}

function scenePage(s, i) {
  const prev = SCENES[i - 1], next = SCENES[i + 1];
  return `<div class="qprog" role="progressbar" aria-valuemin="0" aria-valuemax="${SCENES.length}" aria-valuenow="${i + 1}">
      <span style="width:${((i + 1) / SCENES.length) * 100}%"></span></div>
    <article class="scene">
      <span class="label">Scene ${i + 1} of ${SCENES.length}</span>
      <h2>${esc(s.title)}</h2>
      ${s.intro.map(p => `<p>${esc(p)}</p>`).join("")}
      ${s.formula ? `<div class="formula">${katex.renderToString(s.formula, { displayMode: true, throwOnError: false })}</div>` : ""}
      <div class="card lab">
        <div class="stagewrap"></div>
        <div class="controls">${s.controls()}</div>
        <div class="readout" aria-live="polite"></div>
        <p class="live" aria-live="polite"></p>
      </div>
      ${s.extra || ""}
      ${s.after ? `<p>${esc(s.after)}</p>` : ""}
      <p class="takeaway"><b>Takeaway.</b> ${esc(s.takeaway)}</p>
      <div class="qbar">
        ${prev ? `<a class="btn" href="#anova/${prev.slug}">Back</a>` : `<a class="btn" href="#anova">All scenes</a>`}
        ${next ? `<a class="btn primary" href="#anova/${next.slug}">Next: ${esc(next.title.split(":")[0])}</a>` : `<a class="btn primary" href="#anova">Finish</a>`}
      </div>
    </article>`;
}

// Called from route() in explore.js.
function anovaRoute(rest) {
  stages.clear();
  const i = SCENES.findIndex(s => s.slug === rest), s = SCENES[i];
  $("acrumbs").innerHTML = s ? `<a href="#anova">All scenes</a><span aria-hidden="true">›</span><b>${esc(s.title)}</b>` : "";
  if (!s) { $("apage").innerHTML = anovaListPage(); return; }
  $("apage").innerHTML = scenePage(s, i);
  s.mount($("apage").querySelector(".scene"));
}
