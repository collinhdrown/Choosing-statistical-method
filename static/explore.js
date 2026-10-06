/*
 * explore.js — the Explore tests tab.
 *
 * A landing page of test families (stat_engine.TEST_FAMILIES), a page per family, and a page
 * per test with its card details and color-coded equations. Uses the catalog, esc, slug and
 * colorFor from app.js. Routes live in the URL hash:
 *   #explore                 all families
 *   #explore/family/<slug>   one family
 *   #explore/<slug>          one test
 * The Quiz yourself tab (#quiz...) is drawn by quiz.js and the ANOVA Frogs (#anova...) by anova.js;
 * route() hands them off.
 */
const famBySlug = {}, testBySlug = {};

// \ca{...} .. \cf{...} in an equation paint a term with color a-f; [a:...] in its words does the same.
const KATEX_OPTS = {
  displayMode: true, throwOnError: false, strict: "ignore",
  trust: ctx => ctx.command === "\\htmlClass",
  macros: Object.fromEntries([..."abcdef"].map(c => [`\\c${c}`, `\\htmlClass{eq-${c}}{#1}`])),
};

// The words use the same shapes as the math: \frac{top}{bottom} stacks, \sqrt{...} gets a root bar.
function words(text) {
  let i = 0;
  const group = () => { i++; const out = parse("}"); i++; return out; };   // reads {...}
  function parse(stop) {
    let out = "";
    while (i < text.length && text[i] !== stop) {
      if (text.startsWith("\\frac{", i)) {
        i += 5;
        const top = group(), bottom = group();
        out += `<span class="wfrac"><span class="top">${top}</span><span class="bottom">${bottom}</span></span>`;
      } else if (text.startsWith("\\sqrt{", i)) {
        i += 5;
        out += `<span class="wsqrt"><span class="rad" aria-hidden="true">√</span><span class="under">${group()}</span></span>`;
      } else if (/^\[[a-f]:/.test(text.slice(i, i + 3))) {
        const c = text[i + 1];
        i += 3;
        out += `<span class="eq-${c}">${parse("]")}</span>`;
        i++;
      } else {
        out += esc(text[i++]);
      }
    }
    return out;
  }
  return parse(null);
}

function mathHTML(tex) {
  if (!window.katex) return `<code>${esc(tex)}</code>`;   // CDN unreachable: show the source
  return katex.renderToString(tex, KATEX_OPTS);
}

/* ========== pages ========== */
function testChip(name) {
  return `<a class="xchip" href="#explore/${slug(name)}" style="--card:${colorFor(name)}">${esc(name)}</a>`;
}

function familiesPage() {
  return `<div class="xintro"><h2>Explore tests</h2>
      <p>Pick a family or jump straight to a test. Each test page shows when to use it, an example, and the equations behind it in symbols and in words.</p></div>
    <div class="famgrid">${catalog.families.map(f => `
      <section class="card famcard">
        <a class="famname" href="#explore/family/${slug(f.name)}">${esc(f.name)}</a>
        <p>${esc(f.blurb)}</p>
        <div class="chips">${f.tests.map(testChip).join("")}</div>
      </section>`).join("")}</div>`;
}

function familyPage(f) {
  return `<div class="xintro"><span class="label">Family</span><h2>${esc(f.name)}</h2><p>${esc(f.blurb)}</p></div>
    <div class="famlist">${f.tests.map(n => { const t = byName[n]; return `
      <a class="card famrow" href="#explore/${slug(n)}" style="--card:${colorFor(n)}">
        <h3>${esc(n)}</h3><p>${esc(t.summary)}</p></a>`; }).join("")}</div>`;
}

function testPage(t) {
  const fam = catalog.families.find(f => f.name === t.family);
  const others = fam.tests.filter(n => n !== t.name);
  return `<article class="xtest" style="--card:${colorFor(t.name)}">
    <header class="band">
      <a class="famlink" href="#explore/family/${slug(fam.name)}">${esc(fam.name)}</a>
      <h2>${esc(t.name)}</h2>
      <p>${esc(t.summary)}</p>
    </header>
    <div class="xgrid">
      <section class="card">
        <span class="label">When to use it</span>
        ${t.requirements.length ? `<dl>${t.requirements.map(r =>
          `<dt>${esc(r.short)}</dt><dd>${r.values.map(esc).join('<span class="or">or</span>')}</dd>`).join("")}</dl>` : ""}
        ${t.note ? `<p class="note">${esc(t.note)}</p>` : ""}
      </section>
      <section class="card example">
        <span class="label">Real-world example</span>
        <p>${esc(t.example)}</p>
      </section>
    </div>
    <section class="eqs">
      <h3>The equations</h3>
      <p class="sub">Each color marks the same piece in the symbols and in the words.</p>
      ${t.equations.map(eq => `
        <div class="card eq">
          <span class="label">${esc(eq.label)}</span>
          <div class="math">${mathHTML(eq.math)}</div>
          <div class="words"><span class="tag">In words</span><p>${words(eq.words)}</p></div>
        </div>`).join("")}
    </section>
    ${others.length ? `<section class="others"><span class="label">More in ${esc(fam.name)}</span>
      <div class="chips">${others.map(testChip).join("")}</div></section>` : ""}
  </article>`;
}

/* ========== routing ========== */
const TAGLINES = {
  match: "Answer one question at a time, or describe your study in words. Every answer knocks out the tests that no longer fit.",
  explore: "Browse every test in the catalog: what it is for, when it applies, and the math behind it.",
  quiz: "Practice spotting scales, variables and the right method, then check what you missed.",
  anova: "See what variance is and how the ANOVA family works, with animals you can make hop.",
};

function route() {
  const h = decodeURIComponent(location.hash.slice(1));
  const tab = ["explore", "quiz", "anova"].find(t => h === t || h.startsWith(t + "/")) || "match";
  const explore = tab === "explore";
  $("view-match").hidden = tab !== "match";
  $("view-explore").hidden = tab !== "explore";
  $("view-quiz").hidden = tab !== "quiz";
  $("view-anova").hidden = tab !== "anova";
  $("stat").hidden = tab !== "match";
  $("tagline").textContent = TAGLINES[tab];
  for (const a of document.querySelectorAll(".tab")) {
    const on = a.dataset.tab === tab;
    a.classList.toggle("on", on);
    if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  }
  hideCard();
  if (tab === "quiz") { quizRoute(h.slice("quiz/".length)); scrollTo({ top: 0, behavior: "instant" }); return; }
  if (tab === "anova") { anovaRoute(h.slice("anova/".length)); scrollTo({ top: 0, behavior: "instant" }); return; }
  if (!explore) { if (view) render(); return; }   // the bubble labels need a visible field to measure

  const rest = h.slice("explore/".length);
  const fam = rest.startsWith("family/") ? famBySlug[rest.slice(7)] : null;
  const test = testBySlug[rest];
  const crumbFam = test ? catalog.families.find(f => f.name === test.family) : fam;
  $("crumbs").innerHTML = crumbFam ? `<a href="#explore">All tests</a><span aria-hidden="true">›</span>` +
    (test ? `<a href="#explore/family/${slug(crumbFam.name)}">${esc(crumbFam.name)}</a><span aria-hidden="true">›</span><b>${esc(test.name)}</b>`
          : `<b>${esc(crumbFam.name)}</b>`) : "";
  $("xpage").innerHTML = test ? testPage(test) : fam ? familyPage(fam) : familiesPage();
  scrollTo({ top: 0, behavior: "instant" });
}

catalogReady.then(() => {
  for (const f of catalog.families) famBySlug[slug(f.name)] = f;
  for (const t of catalog.tests) testBySlug[slug(t.name)] = t;
  addEventListener("hashchange", route);
  route();
});
