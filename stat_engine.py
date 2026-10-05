"""
stat_engine.py — single source of truth for the stat-test advisor.

HOW IT WORKS
  * ATTRIBUTES  = the questions you can ask, in priority order (this ORDER is your decision hierarchy).
  * TESTS       = the catalog. Each test lists the answer-combinations ("paths") where it applies.
  * recommend() = filters the catalog by the answers so far. One test left -> done.
                  Several left -> ask the highest-priority attribute that would actually narrow them.

Nothing else contains statistical logic. The UI, the LLM extractor, the question text and the
tree diagram are all generated from these two lists, so they can never disagree.

TO ADD A TEST       -> one add_test(...) call.
TO ADD A QUESTION   -> one Attribute(...) in ATTRIBUTES (position = priority) + reference it in tests.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import os

# ========================================================
# 1. ATTRIBUTES  (order = the decision hierarchy)
# ========================================================
@dataclass(frozen=True)
class Attribute:
    key: str
    short: str                 # label used in diagrams
    question: str              # asked to the user
    options: dict              # value -> human label (ordered)
    hint: str = ""             # examples shown under the question


ATTRIBUTES: list[Attribute] = [
    Attribute("purpose", "Goal", "What is the main goal of your analysis?", {
        "difference": "Compare groups or conditions",
        "association": "See whether variables are related",
        "prediction": "Predict an outcome from predictors",
    }),
    Attribute("dv_count", "Outcomes", "How many outcome (dependent) variables do you have?", {
        "one": "One", "many": "More than one"}),
    Attribute("dv_type", "Outcome scale", "How is your outcome variable measured?", {
        "nominal": "Categories (nominal)",
        "ordinal": "Ranked scale (ordinal)",
        "continuous": "Continuous numbers (interval/ratio)"},
        hint="Yes/No or group labels = categories; 1-5 ratings = ranked; height, GPA, income = continuous."),
    Attribute("iv_count", "Predictors", "How many independent variables (grouping or predictor variables)?", {
        "one": "One", "many": "More than one"}),
    Attribute("iv_type", "Predictor scale", "How are your independent variables measured?", {
        "nominal": "Categories (nominal)",
        "ordinal": "Ranked scale (ordinal)",
        "continuous": "Continuous numbers (interval/ratio)",
        "mixed": "A mix"}),
    Attribute("groups", "Groups", "How many groups or conditions are being compared?", {
        "two": "Exactly two", "three_plus": "Three or more"}),
    Attribute("pairing", "Design", "Are the groups independent or repeated/matched?", {
        "independent": "Independent (different people in each group)",
        "repeated": "Repeated / matched (same people measured again)"}),
    Attribute("covariates", "Covariates", "Do you need to control for continuous covariates (e.g. baseline score)?", {
        "no": "No", "yes": "Yes"}),
    Attribute("nested", "Nesting", "Is your data nested or clustered?", {
        "no": "No", "yes": "Yes"},
        hint="e.g. students within schools, patients within clinics, repeated rows per person in a multilevel design."),
    Attribute("normal", "Normality", "Is your outcome approximately normally distributed?", {
        "yes": "Yes (parametric)", "no": "No (non-parametric)"},
        hint="Check with Shapiro-Wilk, a histogram, or a Q-Q plot."),
]
ATTR = {a.key: a for a in ATTRIBUTES}

# Answer combinations that cannot occur in real data. They are skipped in diagrams and validation
# so they don't show up as "coverage gaps". Add a rule here instead of writing a dummy test.
IMPOSSIBLE: list[dict] = [
    {"iv_count": "one", "iv_type": "mixed"},      # "a mix" of predictors needs 2+ predictors
]


# ========================================================
# 2. TEST CATALOG
# ========================================================
@dataclass
class Test:
    name: str
    paths: list            # each path: {attribute_key: frozenset(allowed values)}; missing key = "any"
    note: str = ""


TESTS: list[Test] = []


def _parse(path: dict) -> dict:
    """Accept 'a|b' strings; validate keys/values so typos fail at import time, not in production."""
    out = {}
    for k, v in path.items():
        if k not in ATTR:
            raise ValueError(f"Unknown attribute '{k}'")
        vals = frozenset(str(v).split("|"))
        bad = vals - set(ATTR[k].options)
        if bad:
            raise ValueError(f"Attribute '{k}' has no option(s) {sorted(bad)}")
        out[k] = vals
    return out


def add_test(name: str, *paths: dict, note: str = "") -> None:
    if any(t.name == name for t in TESTS):
        raise ValueError(f"Duplicate test name: {name}")
    TESTS.append(Test(name, [_parse(p) for p in paths], note))


# Helpers: most tests come in a parametric / non-parametric pair
def param(base: dict) -> dict:
    """Continuous outcome that meets normality."""
    return {**base, "dv_type": "continuous", "normal": "yes"}


def nonparam(base: dict) -> list:
    """Ordinal outcome, OR continuous outcome that fails normality."""
    return [{**base, "dv_type": "ordinal"}, {**base, "dv_type": "continuous", "normal": "no"}]


# ---- Differences: one IV, one DV ------------------------------------------------
DIFF1 = dict(purpose="difference", dv_count="one", iv_count="one", iv_type="nominal", covariates="no", nested="no")
TWO_IND = {**DIFF1, "groups": "two", "pairing": "independent"}
TWO_REP = {**DIFF1, "groups": "two", "pairing": "repeated"}
K_IND = {**DIFF1, "groups": "three_plus", "pairing": "independent"}
K_REP = {**DIFF1, "groups": "three_plus", "pairing": "repeated"}
# a categorical IV with 3+ levels vs a numeric DV, framed as "association"
ASSOC1 = dict(purpose="association", dv_count="one", iv_count="one", nested="no")
A_NOM3 = {**ASSOC1, "iv_type": "nominal", "groups": "three_plus"}
A_NOM2 = {**ASSOC1, "iv_type": "nominal", "groups": "two"}

add_test("Independent Samples t-test", param(TWO_IND))
add_test("Mann-Whitney U Test", *nonparam(TWO_IND))
add_test("Paired Samples t-test", param(TWO_REP))
add_test("Wilcoxon Signed-Rank Test", *nonparam(TWO_REP))
add_test("One-Way ANOVA", param(K_IND), param(A_NOM3))
add_test("Kruskal-Wallis H Test", *nonparam(K_IND), *nonparam(A_NOM3))
add_test("Repeated Measures ANOVA", param(K_REP))
add_test("Friedman Test", *nonparam(K_REP))

# ---- Differences: categorical outcome ---------------------------------------------
NOMDV = dict(purpose="difference", dv_count="one", dv_type="nominal", iv_count="one", iv_type="nominal", covariates="no")
add_test("Chi-Square Test of Independence",
         {**NOMDV, "pairing": "independent"},
         {**ASSOC1, "iv_type": "nominal", "dv_type": "nominal"})
add_test("McNemar's Test", {**NOMDV, "groups": "two", "pairing": "repeated"})
add_test("Cochran's Q Test", {**NOMDV, "groups": "three_plus", "pairing": "repeated"})

# ---- Differences: several IVs (factorial) and covariates --------------------------------
FACT = dict(purpose="difference", dv_count="one", iv_count="many", iv_type="nominal", covariates="no", nested="no")
add_test("Factorial ANOVA", param({**FACT, "pairing": "independent"}))
add_test("Mixed / Repeated-Measures Factorial ANOVA", param({**FACT, "pairing": "repeated"}))
add_test("Aligned Rank Transform (ART) ANOVA", *nonparam(FACT))

COV = dict(purpose="difference", dv_count="one", iv_count="one|many", iv_type="nominal", covariates="yes", nested="no")
add_test("ANCOVA", param({**COV, "pairing": "independent"}))
add_test("Quade's Nonparametric ANCOVA", *nonparam({**COV, "pairing": "independent"}))
add_test("Linear Mixed-Effects Model", {**COV, "pairing": "repeated", "dv_type": "continuous"})

# ---- Differences: several DVs (multivariate) ------------------------------------------
MV = dict(purpose="difference", dv_count="many", dv_type="continuous", iv_type="nominal", nested="no", pairing="independent")
add_test("One-Way MANOVA", {**MV, "iv_count": "one", "covariates": "no", "normal": "yes"})
add_test("Factorial MANOVA", {**MV, "iv_count": "many", "covariates": "no", "normal": "yes"})
add_test("MANCOVA", {**MV, "iv_count": "one|many", "covariates": "yes", "normal": "yes"})
add_test("PERMANOVA (non-parametric MANOVA)", {**MV, "iv_count": "one|many", "normal": "no"})

# ---- Nested / clustered data ---------------------------------------------------------
add_test("Hierarchical Linear Model (HLM)",
         {"purpose": "difference", "dv_count": "one", "dv_type": "continuous", "iv_type": "nominal", "nested": "yes"},
         {"purpose": "association|prediction", "dv_count": "one", "dv_type": "continuous", "nested": "yes"})

# ---- Association (one IV, one DV) ---------------------------------------------------
A1 = {**ASSOC1}
add_test("Pearson's r Correlation", param({**A1, "iv_type": "continuous"}))
add_test("Spearman's Rank Correlation",
         {**A1, "iv_type": "ordinal", "dv_type": "ordinal|continuous"},
         {**A1, "iv_type": "continuous", "dv_type": "ordinal"},
         {**A1, "iv_type": "continuous", "dv_type": "continuous", "normal": "no"})
add_test("Point-Biserial Correlation", param(A_NOM2),
         {**A1, "iv_type": "continuous", "dv_type": "nominal"})
add_test("Rank-Biserial Correlation", *nonparam(A_NOM2))

# ---- Association / prediction with several predictors, and prediction ---------------------
REG = dict(dv_count="one", nested="no")
add_test("Simple Linear Regression", {**REG, "purpose": "prediction", "iv_count": "one", "dv_type": "continuous"})
add_test("Multiple Linear Regression",
         {**REG, "purpose": "association|prediction", "iv_count": "many", "dv_type": "continuous"})
add_test("Binary Logistic Regression",
         {**REG, "purpose": "association|prediction", "iv_count": "many", "dv_type": "nominal"},
         {**REG, "purpose": "prediction", "iv_count": "one", "dv_type": "nominal"},
         {**REG, "purpose": "association", "iv_count": "one", "iv_type": "ordinal", "dv_type": "nominal"},
         {"purpose": "difference", "dv_count": "one", "dv_type": "nominal", "iv_type": "nominal", "covariates": "yes"})
add_test("Ordinal Logistic Regression",
         {**REG, "purpose": "association", "iv_count": "many", "dv_type": "ordinal"},
         {**REG, "purpose": "prediction", "dv_type": "ordinal"})
add_test("Multivariate Multiple Regression",
         {"purpose": "prediction", "dv_count": "many", "dv_type": "continuous", "nested": "no"})
add_test("Canonical Correlation Analysis",
         {"purpose": "association", "dv_count": "many", "dv_type": "continuous", "nested": "no"})


# ---- Test cards: one-sentence summary + a real-world example, shown on hover in the web app.
# Every test in the catalog needs an entry; a missing or stray name fails at import time.
TEST_INFO: dict[str, tuple[str, str]] = {
    "Independent Samples t-test": (
        "Compares the means of two separate groups on a normally distributed outcome.",
        "Comparing average exam scores of students taught online versus in person."),
    "Mann-Whitney U Test": (
        "Compares two separate groups when the outcome is ranked or not normally distributed.",
        "Comparing pain ratings (0-10) between patients given a new drug and a placebo."),
    "Paired Samples t-test": (
        "Compares two measurements from the same people on a normally distributed outcome.",
        "Comparing blood pressure in the same patients before and after a diet program."),
    "Wilcoxon Signed-Rank Test": (
        "Compares two measurements from the same people when the outcome is ranked or skewed.",
        "Comparing anxiety scores of the same students before and after a mindfulness course."),
    "One-Way ANOVA": (
        "Compares the means of three or more separate groups on a normally distributed outcome.",
        "Comparing crop yield across fields treated with three different fertilizers."),
    "Kruskal-Wallis H Test": (
        "Compares three or more separate groups when the outcome is ranked or not normally distributed.",
        "Comparing customer satisfaction ratings across four store locations."),
    "Repeated Measures ANOVA": (
        "Compares the means of three or more measurements taken on the same people.",
        "Tracking reaction time in the same drivers after 0, 1 and 2 drinks."),
    "Friedman Test": (
        "Compares three or more measurements on the same people when the outcome is ranked or skewed.",
        "Having the same tasters rank three coffee blends."),
    "Chi-Square Test of Independence": (
        "Tests whether two categorical variables are related by comparing observed and expected counts.",
        "Checking whether voting preference differs between age groups."),
    "McNemar's Test": (
        "Compares a yes/no outcome measured twice on the same people.",
        "Checking whether more people pass a driving test after a refresher course than before."),
    "Cochran's Q Test": (
        "Compares a yes/no outcome measured three or more times on the same people.",
        "Checking whether the same users complete a task on three website designs."),
    "Factorial ANOVA": (
        "Tests the effects of two or more grouping factors, and their interaction, on one outcome.",
        "Testing how teaching method and class size together affect test scores."),
    "Mixed / Repeated-Measures Factorial ANOVA": (
        "Tests several factors when at least one is measured repeatedly on the same people.",
        "Comparing therapy and control groups on depression scores at three time points."),
    "Aligned Rank Transform (ART) ANOVA": (
        "Runs a factorial ANOVA on aligned ranks, for ranked or non-normal outcomes with several factors.",
        "Testing how font and screen size together affect 1-7 readability ratings."),
    "ANCOVA": (
        "Compares group means while adjusting for a continuous covariate such as a baseline score.",
        "Comparing final scores across tutoring programs while controlling for pre-test scores."),
    "Quade's Nonparametric ANCOVA": (
        "Compares groups while adjusting for a covariate, without assuming a normal outcome.",
        "Comparing skewed hospital stay lengths across treatments, adjusting for patient age."),
    "Linear Mixed-Effects Model": (
        "Models repeated measurements with fixed effects and random effects for each person, including covariates.",
        "Modeling weekly weight across diet groups while adjusting for starting weight."),
    "One-Way MANOVA": (
        "Compares groups on several related continuous outcomes at once.",
        "Comparing three training programs on both speed and endurance."),
    "Factorial MANOVA": (
        "Tests two or more grouping factors on several related continuous outcomes at once.",
        "Testing how sleep schedule and caffeine affect both memory and attention scores."),
    "MANCOVA": (
        "Compares groups on several continuous outcomes while adjusting for a covariate.",
        "Comparing reading and math scores across schools while controlling for family income."),
    "PERMANOVA (non-parametric MANOVA)": (
        "Compares groups on several outcomes using permutations, without assuming normality.",
        "Comparing gut microbiome composition between diet groups."),
    "Hierarchical Linear Model (HLM)": (
        "Models an outcome when observations are nested within groups, such as students within schools.",
        "Studying how teacher experience affects student scores across 40 schools."),
    "Pearson's r Correlation": (
        "Measures the strength of a straight-line relationship between two normally distributed variables.",
        "Measuring how strongly height and weight are related in adults."),
    "Spearman's Rank Correlation": (
        "Measures how consistently two variables rise or fall together using their ranks.",
        "Relating class rank to self-rated confidence (1-5)."),
    "Point-Biserial Correlation": (
        "Measures the relationship between a two-category variable and a continuous variable.",
        "Relating smoker status (yes/no) to lung capacity."),
    "Rank-Biserial Correlation": (
        "Measures the relationship between a two-category variable and a ranked or skewed variable.",
        "Relating gender to 1-5 agreement ratings on a survey item."),
    "Simple Linear Regression": (
        "Predicts a continuous outcome from one predictor with a straight line.",
        "Predicting monthly electricity cost from average temperature."),
    "Multiple Linear Regression": (
        "Predicts a continuous outcome from several predictors at once.",
        "Predicting house price from size, age and neighborhood."),
    "Binary Logistic Regression": (
        "Predicts the probability of a yes/no outcome from one or more predictors.",
        "Predicting whether a patient is readmitted within 30 days from age and diagnosis."),
    "Ordinal Logistic Regression": (
        "Predicts an ordered outcome, such as low, medium or high, from predictors.",
        "Predicting a 1-5 customer rating from wait time and price."),
    "Multivariate Multiple Regression": (
        "Predicts several continuous outcomes at once from the same set of predictors.",
        "Predicting both GPA and graduation time from study hours and work hours."),
    "Canonical Correlation Analysis": (
        "Finds the strongest relationships between two sets of continuous variables.",
        "Relating a set of personality scores to a set of job performance measures."),
}
if set(TEST_INFO) != {t.name for t in TESTS}:
    raise ValueError(f"TEST_INFO and TESTS disagree: {set(TEST_INFO) ^ {t.name for t in TESTS}}")


def requirements(test: Test) -> list[tuple[str, list[str]]]:
    """What a test needs, in question order: (attribute short label, allowed option labels).

    Merges all of the test's paths; an attribute any path leaves open is left out."""
    out = []
    for attr in ATTRIBUTES:
        if not all(attr.key in p for p in test.paths):
            continue
        allowed = set().union(*(p[attr.key] for p in test.paths))
        out.append((attr.short, [lbl for v, lbl in attr.options.items() if v in allowed]))
    return out


# ========================================================
# 3. ENGINE
# ========================================================
def _answered(state: dict) -> dict:
    """Only keep answers that are valid options. None / 'Unselected' / junk from the LLM are ignored."""
    return {k: v for k, v in (state or {}).items() if k in ATTR and v in ATTR[k].options}


def _path_ok(path: dict, answers: dict) -> bool:
    return all(answers[k] in allowed for k, allowed in path.items() if k in answers)


def valid_options(attr: Attribute, answers: dict) -> dict:
    """Options of `attr` that don't contradict an IMPOSSIBLE rule given the answers so far."""
    def ok(v):
        trial = {**answers, attr.key: v}
        return not any(all(trial.get(k) == val for k, val in rule.items()) for rule in IMPOSSIBLE)
    return {v: lbl for v, lbl in attr.options.items() if ok(v)}


def candidates(state: dict) -> list[Test]:
    a = _answered(state)
    return [t for t in TESTS if any(_path_ok(p, a) for p in t.paths)]


def next_question(state: dict) -> Attribute | None:
    """Highest-priority unanswered attribute whose answer would change the candidate list."""
    a = _answered(state)
    current = frozenset(t.name for t in candidates(a))
    for attr in ATTRIBUTES:
        if attr.key in a:
            continue
        outcomes = {frozenset(t.name for t in candidates({**a, attr.key: v})) for v in valid_options(attr, a)}
        outcomes.discard(frozenset())
        if outcomes != {current}:
            return attr
    return None


def explain_conflicts(state: dict) -> list[str]:
    """When nothing matches: which single answers, if removed, would restore a match."""
    a = _answered(state)
    return [k for k in a if candidates({kk: vv for kk, vv in a.items() if kk != k})]


def canonicalize(state: dict) -> dict:
    """The one 'current state' both the form and the chatbot should reason from.

    Walks ATTRIBUTES in the engine's own priority order and keeps an answer only if it's
    still a legal option (per valid_options) given everything kept before it. An answer for
    a question that hasn't come up yet, or one that's now impossible because an earlier
    answer changed, is silently dropped rather than corrupting the recommendation — exactly
    what the form's dropdown loop already guarantees by construction, now available to any
    caller (chat included) with plain data, no widgets required.
    """
    given = _answered(state)
    canon: dict = {}
    for _ in range(len(ATTRIBUTES) + 1):
        result = recommend(canon)
        if result["status"] != "incomplete":
            break
        key = result["ask_for"]
        if key not in given or given[key] not in valid_options(ATTR[key], canon):
            break
        canon[key] = given[key]
    return canon


def recommend(state: dict) -> dict:
    cands = candidates(state)
    if not cands:
        return {"status": "no_match", "conflicts": explain_conflicts(state)}
    if len(cands) == 1:
        return {"status": "complete", "test": cands[0].name, "note": cands[0].note}
    attr = next_question(state)
    if attr is None:
        return {"status": "ambiguous", "tests": [t.name for t in cands]}
    return {"status": "incomplete", "ask_for": attr.key, "remaining": [t.name for t in cands]}


evaluate_decision_tree = recommend      # drop-in name for existing imports


# ========================================================
# 4. GLUE: LLM extraction + UI, both generated from ATTRIBUTES
# ========================================================
def extraction_model():
    """Pydantic model for client.beta.chat.completions.parse(response_format=...).
    Every field is Optional[Literal[...]] so the LLM can only return valid vocabulary."""
    from typing import Literal, Optional
    from pydantic import create_model
    fields = {a.key: (Optional[Literal[tuple(a.options)]], None) for a in ATTRIBUTES}
    return create_model("ExtractedState", **fields)


def extraction_prompt(current_state: dict) -> str:
    lines = ["You extract study-design facts from a conversation about choosing a statistical test.",
             "Only fill a field if the user clearly stated or unambiguously implied it; otherwise leave it null.",
             "Standard metrics such as GPA, test scores, IQ, height, weight, age, income are continuous.", ""]
    for a in ATTRIBUTES:
        lines.append(f"- {a.key}: {a.question}  Allowed: " + "; ".join(f"{v} = {lbl}" for v, lbl in a.options.items()))
    lines.append(f"\nAlready known: {_answered(current_state)}")
    return "\n".join(lines)


def merge_state(state: dict, extracted: dict) -> dict:
    """Merge LLM output. Uses `is not None` (NOT truthiness), so 'no' / False answers are kept."""
    merged = dict(state)
    for k, v in extracted.items():
        if k in ATTR and v is not None:
            merged[k] = v
    return merged


def question_for(key: str) -> dict:
    a = ATTR[key]
    return {"question": a.question, "hint": a.hint, "options": a.options}


# ========================================================
# 5. TREE BUILDER, VALIDATOR, DIAGRAM EXPORT
# ========================================================
def build_tree(state: dict | None = None) -> dict:
    """Walks the SAME next_question() the live app uses, so the diagram is the real behaviour."""
    state = _answered(state or {})
    cands = candidates(state)
    if not cands:
        return {"kind": "gap"}
    if len(cands) == 1:
        return {"kind": "leaf", "test": cands[0].name}
    attr = next_question(state)
    if attr is None:
        return {"kind": "ambiguous", "tests": [t.name for t in cands]}
    return {"kind": "question", "attr": attr,
            "children": [(lbl, build_tree({**state, attr.key: v})) for v, lbl in valid_options(attr, state).items()]}


def validate() -> dict:
    """Catalog health check. Run it after every edit (and in CI)."""
    tree = build_tree()
    reached, gaps, ambiguous = set(), [], []

    def walk(node, trail):
        if node["kind"] == "leaf":
            reached.add(node["test"])
        elif node["kind"] == "gap":
            gaps.append(" > ".join(trail))
        elif node["kind"] == "ambiguous":
            ambiguous.append((" > ".join(trail), node["tests"]))
            reached.update(node["tests"])
        else:
            for lbl, child in node["children"]:
                walk(child, trail + [f"{node['attr'].short}={lbl}"])

    walk(tree, [])
    return {"unreachable": sorted({t.name for t in TESTS} - reached), "gaps": gaps, "ambiguous": ambiguous}


def to_mermaid(state: dict | None = None) -> str:
    tree = build_tree(state)
    lines, ids, counter = ["flowchart TD"], {}, [0]

    def new_id():
        counter[0] += 1
        return f"n{counter[0]}"

    def esc(s):
        return str(s).replace('"', "'")

    def emit(node):
        if node["kind"] == "leaf":
            if node["test"] not in ids:                 # leaves merge: same test = one node (a DAG)
                ids[node["test"]] = new_id()
                lines.append(f'  {ids[node["test"]]}(["{esc(node["test"])}"]):::test')
            return ids[node["test"]]
        i = new_id()
        if node["kind"] == "gap":
            lines.append(f'  {i}["No test in catalog yet"]:::gap')
        elif node["kind"] == "ambiguous":
            lines.append(f'  {i}["Ambiguous: {esc(" / ".join(node["tests"]))}"]:::gap')
        else:
            lines.append(f'  {i}{{"{esc(node["attr"].short)}?"}}:::q')
            for lbl, child in node["children"]:
                lines.append(f'  {i} -->|"{esc(lbl)}"| {emit(child)}')
        return i

    emit(tree)
    lines += ["  classDef q fill:#1E3A8A,stroke:#3B82F6,color:#F8FAFC",
              "  classDef test fill:#065F46,stroke:#10B981,color:#ECFDF5",
              "  classDef gap fill:#7F1D1D,stroke:#EF4444,color:#FEE2E2,stroke-dasharray: 4 3"]
    return "\n".join(lines)


def export_diagrams(outdir: str = "diagrams") -> list[str]:
    os.makedirs(outdir, exist_ok=True)
    paths = []
    for purpose in ATTR["purpose"].options:
        p = os.path.join(outdir, f"tree_{purpose}.mermaid")
        with open(p, "w") as f:
            f.write(to_mermaid({"purpose": purpose}))
        paths.append(p)
    return paths


if __name__ == "__main__":
    report = validate()
    print(f"{len(TESTS)} tests in catalog")
    print("Unreachable tests:", report["unreachable"] or "none")
    print("Ambiguous states :", report["ambiguous"] or "none")
    print(f"Coverage gaps    : {len(report['gaps'])}")
    for g in report["gaps"]:
        print("   -", g)
    print("Wrote:", export_diagrams())