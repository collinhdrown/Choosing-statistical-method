/*
 * quiz.js — the Quiz yourself tab.
 *
 * Questions come from /api/quizzes (quiz_bank.py). Answers are kept until the end, then the
 * score and every missed question are shown with the right answer. Uses $, esc and slug from
 * app.js. Routes live in the URL hash:
 *   #quiz           all quizzes
 *   #quiz/<slug>    one quiz
 */
let quizzes = null;
let run = null;   // { quiz, questions, i, picks, done }

const loadQuizzes = () => quizzes ? Promise.resolve(quizzes)
  : api("/api/quizzes").then(data => (quizzes = data));

function shuffled(list) {
  const a = [...list];
  for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
  return a;
}

function startQuiz(quiz) {
  const questions = shuffled(quiz.questions).map(q =>
    quiz.shuffle_options ? { ...q, options: shuffled(q.options) } : q);
  // single: picks[i] is the chosen option; parts: picks[i] is an array, one choice per part
  run = { quiz, questions, i: 0, picks: questions.map(q => q.parts ? q.parts.map(() => null) : null), done: false };
}

const total = r => r.quiz.kind === "parts" ? r.questions.reduce((n, q) => n + q.parts.length, 0) : r.questions.length;
function score(r) {
  if (r.quiz.kind !== "parts") return r.questions.filter((q, i) => r.picks[i] === q.answer).length;
  return r.questions.reduce((n, q, i) => n + q.parts.filter((p, j) => r.picks[i][j] === p.answer).length, 0);
}

/* ========== pages ========== */
function quizListPage() {
  return `<div class="xintro"><h2>Quiz yourself</h2>
      <p>Pick a quiz. You'll see your score at the end, along with the right answer to anything you missed.</p></div>
    <div class="quizgrid">${quizzes.map(q => `
      <a class="card quizcard" href="#quiz/${q.slug}">
        <span class="label">${q.kind === "parts" ? `${q.questions.length} studies` : `${q.questions.length} questions`}</span>
        <h3>${esc(q.title)}</h3>
        <p>${esc(q.blurb)}</p>
      </a>`).join("")}</div>`;
}

function progress(r) {
  const n = r.questions.length;
  return `<div class="qprog" role="progressbar" aria-valuemin="0" aria-valuemax="${n}" aria-valuenow="${r.i}">
    <span style="width:${(r.i / n) * 100}%"></span></div>`;
}

function prompt(quiz, q) {
  return quiz.slug === "scales"
    ? `<p class="qlead">What is the measurement scale of this variable?</p><h2>${esc(q.prompt)}</h2>`
    : `<h2 class="scenario">${esc(q.prompt)}</h2>`;
}

function singlePage(r) {
  const q = r.questions[r.i];
  return `${progress(r)}
    <div class="card q quizq">
      <span class="label">Question ${r.i + 1} of ${r.questions.length}</span>
      ${prompt(r.quiz, q)}
      <div class="opts">${q.options.map((o, k) => `
        <button class="opt ${r.picks[r.i] === o ? "picked" : ""}" style="--i:${k}" data-pick="${k}" type="button">
          <span class="key">${k + 1}</span><span class="t">${esc(o)}</span></button>`).join("")}</div>
      ${r.i ? `<button class="btn back" data-nav="back" type="button">Back</button>` : ""}
    </div>`;
}

function partsPage(r) {
  const q = r.questions[r.i], picks = r.picks[r.i];
  const last = r.i === r.questions.length - 1;
  return `${progress(r)}
    <div class="card q quizq">
      <span class="label">Study ${r.i + 1} of ${r.questions.length}</span>
      <h2 class="scenario">${esc(q.prompt)}</h2>
      ${q.parts.map((p, j) => `
        <fieldset class="part">
          <legend>${esc(p.prompt)}</legend>
          <div class="seg">${p.options.map((o, k) => `
            <button class="segbtn ${picks[j] === o ? "picked" : ""}" data-part="${j}" data-pick="${k}" type="button"
              aria-pressed="${picks[j] === o}">${esc(o)}</button>`).join("")}</div>
        </fieldset>`).join("")}
      <div class="qbar">
        ${r.i ? `<button class="btn" data-nav="back" type="button">Back</button>` : "<span></span>"}
        <button class="btn primary" data-nav="next" type="button" ${picks.every(Boolean) ? "" : "disabled"}>
          ${last ? "See my score" : "Next study"}</button>
      </div>
    </div>`;
}

function answerRows(yours, right, why, test) {
  return `<div class="mrow"><span class="tag no">Your answer</span><span>${esc(yours)}</span></div>
    <div class="mrow"><span class="tag yes">Correct</span><b>${esc(right)}</b></div>
    <p class="why">${esc(why)}${test ? ` <a href="#explore/${slug(test)}">Read about ${esc(test)}</a>` : ""}</p>`;
}

function resultsPage(r) {
  const got = score(r), n = total(r), pct = Math.round((got / n) * 100);
  const misses = [];
  r.questions.forEach((q, i) => {
    if (r.quiz.kind !== "parts") {
      if (r.picks[i] !== q.answer) misses.push(`<li class="card miss">
        <p class="mq">${esc(r.quiz.slug === "scales" ? `What scale is: ${q.prompt}?` : q.prompt)}</p>
        ${answerRows(r.picks[i], q.answer, q.why, q.test)}</li>`);
      return;
    }
    // one card per study: the scenario once, then each part that was missed
    const parts = q.parts.filter((p, j) => r.picks[i][j] !== p.answer);
    if (parts.length) misses.push(`<li class="card miss">
      <p class="mscen"><b>Study ${i + 1}.</b> ${esc(q.prompt)}</p>
      ${parts.map(p => `<div class="mpart"><p class="mq">${esc(p.prompt)}</p>
        ${answerRows(r.picks[i][q.parts.indexOf(p)], p.answer, p.why)}</div>`).join("")}</li>`);
  });
  const verdict = pct === 100 ? "Perfect score." : pct >= 80 ? "Nicely done." : pct >= 50 ? "Getting there." : "Worth another try.";
  return `<div class="card score ${pct >= 80 ? "good" : ""}">
      <span class="label">${esc(r.quiz.title)}</span>
      <div class="big">${got}<small> / ${n}</small></div>
      <p>${verdict} ${r.quiz.kind === "parts" ? "Each part of each study counts as one point." : ""}</p>
      <div class="qbar">
        <button class="btn primary" data-nav="retry" type="button">Try again</button>
        <a class="btn" href="#quiz">Other quizzes</a>
      </div>
    </div>
    ${misses.length ? `<section class="misses"><h3>What you missed</h3><ol>${misses.join("")}</ol></section>` : ""}`;
}

/* ========== routing (called from explore.js) ========== */
function drawQuiz() {
  const r = run;
  $("qpage").innerHTML = r.done ? resultsPage(r) : r.quiz.kind === "parts" ? partsPage(r) : singlePage(r);
}

function quizRoute(rest) {
  loadQuizzes().then(() => {
    const quiz = quizzes.find(q => q.slug === rest);
    $("qcrumbs").innerHTML = quiz ? `<a href="#quiz">All quizzes</a><span aria-hidden="true">›</span><b>${esc(quiz.title)}</b>` : "";
    if (!quiz) { run = null; $("qpage").innerHTML = quizListPage(); return; }
    if (!run || run.quiz !== quiz) startQuiz(quiz);
    drawQuiz();
  }).catch(() => { $("qpage").innerHTML = `<div class="card">The quizzes couldn't load. Refresh the page to try again.</div>`; });
}

function advance() {
  if (run.i < run.questions.length - 1) run.i++; else run.done = true;
  drawQuiz();
  scrollTo({ top: 0, behavior: "instant" });
}

$("view-quiz").addEventListener("click", e => {
  if (!run || run.wait) return;
  const b = e.target.closest("[data-pick], [data-nav]");
  if (!b) return;
  const q = run.questions[run.i];
  if (b.dataset.nav === "back") { run.i--; return drawQuiz(); }
  if (b.dataset.nav === "next") return advance();
  if (b.dataset.nav === "retry") { startQuiz(run.quiz); return drawQuiz(); }
  if (b.dataset.part !== undefined) {
    const j = +b.dataset.part;
    run.picks[run.i][j] = q.parts[j].options[+b.dataset.pick];
    return drawQuiz();
  }
  run.picks[run.i] = q.options[+b.dataset.pick];
  b.classList.add("picked");
  run.wait = true;   // ignore a second click while the pick flashes
  setTimeout(() => { run.wait = false; advance(); }, reduced ? 0 : 160);
});

document.addEventListener("keydown", e => {
  if ($("view-quiz").hidden || !run || run.done || run.quiz.kind === "parts" || e.target.closest("textarea, input")) return;
  const n = parseInt(e.key, 10);
  const btn = n ? document.querySelectorAll("#view-quiz .opt")[n - 1] : null;
  if (btn) btn.click();
});
