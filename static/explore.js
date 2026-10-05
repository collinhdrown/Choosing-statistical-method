/*
 * explore.js — the Explore tests tab.
 *
 * A grouped dropdown (families from stat_engine.TEST_FAMILIES, each opening a flyout of its
 * tests) and one page per test with its card details and color-coded equations. Uses the
 * catalog, esc, slug and colorFor from app.js. Routes live in the URL hash:
 *   #explore                 all families
 *   #explore/family/<slug>   one family
 *   #explore/<slug>          one test
 */
const menu = $("menu"), pick = $("pick");
const famBySlug = {}, testBySlug = {};

// \ca{...} .. \cf{...} in an equation paint a term with color a-f; [a:...] in its words does the same.
const KATEX_OPTS = {
  displayMode: true, throwOnError: false, strict: "ignore",
  trust: ctx => ctx.command === "\\htmlClass",
  macros: Object.fromEntries([..."abcdef"].map(c => [`\\c${c}`, `\\htmlClass{eq-${c}}{#1}`])),
};
const words = text => esc(text).replace(/\[([a-f]):([^\]]+)\]/g, '<span class="eq-$1">$2</span>');

function mathHTML(tex) {
  if (!window.katex) return `<code>${esc(tex)}</code>`;   // CDN unreachable: show the source
  return katex.renderToString(tex, KATEX_OPTS);
}

/* ========== dropdown ========== */
function buildMenu() {
  menu.innerHTML = catalog.families.map(f => `
    <div class="fam" role="none">
      <button class="mi famitem" role="menuitem" type="button" aria-haspopup="menu" aria-expanded="false" data-fam="${slug(f.name)}">
        <span>${esc(f.name)}</span><span class="n">${f.tests.length}</span><span class="arrow" aria-hidden="true">▸</span>
      </button>
      <div class="flyout" role="menu" aria-label="${esc(f.name)}">
        <a class="mi overview" role="menuitem" href="#explore/family/${slug(f.name)}">See the whole family</a>
        ${f.tests.map(n => `<a class="mi" role="menuitem" href="#explore/${slug(n)}">
          <span class="dot" style="background:${colorFor(n)}"></span>${esc(n)}</a>`).join("")}
      </div>
    </div>`).join("");
}

function openMenu(open) {
  menu.hidden = !open;
  pick.setAttribute("aria-expanded", open);
  if (!open) openFam(null);
}

function openFam(famEl) {
  for (const el of menu.querySelectorAll(".fam")) {
    const on = el === famEl;
    el.classList.toggle("open", on);
    el.querySelector(".famitem").setAttribute("aria-expanded", on);
  }
}

pick.addEventListener("click", e => {
  e.stopPropagation();
  openMenu(menu.hidden);
  if (!menu.hidden) menu.querySelector(".famitem").focus();
});

// Hovering a family opens its flyout; clicking (touch) toggles it.
menu.addEventListener("mouseover", e => {
  const fam = e.target.closest(".fam");
  if (fam && matchMedia("(hover: hover)").matches) openFam(fam);
});
menu.addEventListener("click", e => {
  e.stopPropagation();
  const item = e.target.closest(".famitem");
  if (item) { const fam = item.parentElement; openFam(fam.classList.contains("open") ? null : fam); return; }
  if (e.target.closest("a")) openMenu(false);
});
document.addEventListener("click", () => { if (!menu.hidden) openMenu(false); });

// Keyboard: up/down within a list, right/enter into a family, left/escape back out.
menu.addEventListener("keydown", e => {
  const cur = e.target.closest(".mi");
  if (!cur) return;
  const inSub = !!cur.closest(".flyout");
  const list = inSub ? [...cur.closest(".flyout").querySelectorAll(".mi")] : [...menu.querySelectorAll(".famitem")];
  const i = list.indexOf(cur);
  const fam = cur.closest(".fam");
  if (e.key === "ArrowDown") list[(i + 1) % list.length].focus();
  else if (e.key === "ArrowUp") list[(i - 1 + list.length) % list.length].focus();
  else if (!inSub && (e.key === "ArrowRight" || e.key === "Enter" || e.key === " ")) {
    openFam(fam); fam.querySelector(".flyout .mi").focus();
  } else if (inSub && e.key === "ArrowLeft") { openFam(null); fam.querySelector(".famitem").focus(); }
  else if (e.key === "Escape") { openMenu(false); pick.focus(); }
  else return;
  e.preventDefault();
});

/* ========== pages ========== */
function testChip(name) {
  return `<a class="xchip" href="#explore/${slug(name)}" style="--card:${colorFor(name)}">${esc(name)}</a>`;
}

function familiesPage() {
  return `<div class="xintro"><h2>Explore tests</h2>
      <p>Pick a family from the menu, or jump straight to a test below. Each test page shows when to use it, an example, and the equations behind it in symbols and in words.</p></div>
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
function route() {
  const h = decodeURIComponent(location.hash.slice(1));
  const explore = h === "explore" || h.startsWith("explore/");
  $("view-match").hidden = explore;
  $("view-explore").hidden = !explore;
  $("stat").hidden = explore;
  $("tagline").textContent = explore
    ? "Browse every test in the catalog: what it is for, when it applies, and the math behind it."
    : "Answer one question at a time, or describe your study in words. Every answer knocks out the tests that no longer fit.";
  for (const a of document.querySelectorAll(".tab")) {
    const on = (a.dataset.tab === "explore") === explore;
    a.classList.toggle("on", on);
    if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  }
  hideCard();
  openMenu(false);
  if (!explore) { if (view) render(); return; }   // the bubble labels need a visible field to measure

  const rest = h.slice("explore/".length);
  const fam = rest.startsWith("family/") ? famBySlug[rest.slice(7)] : null;
  const test = testBySlug[rest];
  $("picklabel").textContent = test ? test.name : fam ? fam.name : "Choose a test";
  $("xpage").innerHTML = test ? testPage(test) : fam ? familyPage(fam) : familiesPage();
  scrollTo({ top: 0, behavior: "instant" });
}

catalogReady.then(() => {
  for (const f of catalog.families) famBySlug[slug(f.name)] = f;
  for (const t of catalog.tests) testBySlug[slug(t.name)] = t;
  buildMenu();
  addEventListener("hashchange", route);
  route();
});
