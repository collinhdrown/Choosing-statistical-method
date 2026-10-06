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
    hint: str = ""             # examples shown behind the question's "?" help icon
    infer: str = ""            # extra guidance for the LLM on when the answer is already implied


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
    Attribute("nested", "Nesting", "Is your data nested?", {
        "no": "No", "yes": "Yes"},
        hint="Nested means observations share a higher-level unit, so they aren't independent of each other: "
             "students within schools, patients within clinics, or several rows per person in a multilevel "
             "design. If every row is a separate, unrelated individual measured once, it isn't nested.",
        infer="Answer 'no' when the description makes each observation a separate, unrelated unit measured once "
              "with no shared grouping: e.g. predicting one animal's or person's value from population or "
              "reference data for its breed or group, a single random sample of people each measured once, "
              "or published summary data. Answer 'yes' only when observations are grouped inside higher-level "
              "units (classrooms, schools, clinics, litters, sites, families) or several rows come from the same "
              "unit in a multilevel design. A plain two-condition before/after or matched design is handled by "
              "the repeated/matched question, not by nesting. If the grouping structure is unclear, leave it null."),
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


# ---- Families: how the Explore tab groups the tests in its dropdown. Every test belongs to
# exactly one family; a missing, stray or doubled name fails at import time.
TEST_FAMILIES: list[tuple[str, str, list[str]]] = [
    ("t-tests", "Compare the means of two groups or two measurements on a normally distributed outcome.", [
        "Independent Samples t-test", "Paired Samples t-test"]),
    ("ANOVA Family", "Split the variation in one or more outcomes into parts explained by groups, factors and covariates.", [
        "One-Way ANOVA", "Repeated Measures ANOVA", "Factorial ANOVA",
        "Mixed / Repeated-Measures Factorial ANOVA", "ANCOVA",
        "One-Way MANOVA", "Factorial MANOVA", "MANCOVA", "PERMANOVA (non-parametric MANOVA)"]),
    ("Rank-Based Comparisons", "Compare groups using ranks instead of raw values, for ranked or skewed outcomes.", [
        "Mann-Whitney U Test", "Wilcoxon Signed-Rank Test", "Kruskal-Wallis H Test", "Friedman Test",
        "Aligned Rank Transform (ART) ANOVA", "Quade's Nonparametric ANCOVA"]),
    ("Categorical Outcomes", "Compare counts and proportions when the outcome is a category such as yes/no.", [
        "Chi-Square Test of Independence", "McNemar's Test", "Cochran's Q Test"]),
    ("Correlation", "Measure how strongly two variables, or two sets of variables, move together.", [
        "Pearson's r Correlation", "Spearman's Rank Correlation", "Point-Biserial Correlation",
        "Rank-Biserial Correlation", "Canonical Correlation Analysis"]),
    ("Regression & Mixed Models", "Model an outcome as an equation of its predictors.", [
        "Simple Linear Regression", "Multiple Linear Regression", "Binary Logistic Regression",
        "Ordinal Logistic Regression", "Multivariate Multiple Regression",
        "Linear Mixed-Effects Model", "Hierarchical Linear Model (HLM)"]),
]
_in_families = [n for _, _, names in TEST_FAMILIES for n in names]
if sorted(_in_families) != sorted(t.name for t in TESTS):
    raise ValueError(f"TEST_FAMILIES and TESTS disagree: {set(_in_families) ^ {t.name for t in TESTS}}")


# ---- Equations shown on each test's Explore page: (label, LaTeX, the same equation in words).
# Color coding: in the LaTeX, \ca{...} through \cf{...} paint a term with color a-f; in the words,
# [a:...] paints the matching phrase the same color, so each symbol lines up with its meaning.
# The words also use \frac{top}{bottom} and \sqrt{...}, drawn as stacked fractions and roots like the math.
TEST_EQUATIONS: dict[str, list[tuple[str, str, str]]] = {
    "Independent Samples t-test": [
        ("Test statistic",
         r"t = \frac{\ca{\bar{x}_1 - \bar{x}_2}}{\cb{s_p}\sqrt{\cc{\tfrac{1}{n_1} + \tfrac{1}{n_2}}}}",
         r"t = \frac{[a:difference between the two group means]}{[b:pooled standard deviation] × \sqrt{[c:\frac{1}{size of group 1} + \frac{1}{size of group 2}]}}"),
        ("Pooled standard deviation",
         r"\cb{s_p} = \sqrt{\frac{\cd{(n_1-1)s_1^2 + (n_2-1)s_2^2}}{\ce{n_1 + n_2 - 2}}}",
         r"[b:pooled standard deviation] = \sqrt{\frac{[d:each group's variance, weighted by its size]}{[e:degrees of freedom: total sample size − 2]}}"),
        ("Effect size (Cohen's d)",
         r"d = \frac{\ca{\bar{x}_1 - \bar{x}_2}}{\cb{s_p}}",
         r"d = \frac{[a:difference between the group means]}{[b:pooled standard deviation]}"),
    ],
    "Paired Samples t-test": [
        ("Test statistic",
         r"t = \frac{\ca{\bar{d}}}{\cb{s_d} / \sqrt{\cc{n}}}",
         r"t = \frac{[a:average of each person's before-after difference]}{[b:standard deviation of those differences] / \sqrt{[c:number of pairs]}}"),
        ("Effect size (Cohen's d_z)",
         r"d_z = \frac{\ca{\bar{d}}}{\cb{s_d}}",
         r"d = \frac{[a:average difference]}{[b:standard deviation of the differences]}"),
    ],
    "Mann-Whitney U Test": [
        ("U statistic",
         r"U_1 = \ca{R_1} - \cb{\frac{n_1(n_1+1)}{2}}",
         "U = [a:sum of group 1's ranks in the combined data] − [b:smallest rank sum group 1 could possibly have]"),
        ("Large-sample z",
         r"z = \frac{U - \cc{\tfrac{n_1 n_2}{2}}}{\cd{\sqrt{\tfrac{n_1 n_2 (n_1 + n_2 + 1)}{12}}}}",
         r"z = \frac{U − [c:U expected if the groups don't differ]}{[d:standard error of U]}"),
    ],
    "Wilcoxon Signed-Rank Test": [
        ("W statistic",
         r"W = \sum_{\ca{d_i > 0}} \cb{R_i}",
         "W = add up the [b:ranks of the absolute differences] for the [a:pairs whose difference is positive]"),
        ("Large-sample z",
         r"z = \frac{W - \cc{\tfrac{n(n+1)}{4}}}{\cd{\sqrt{\tfrac{n(n+1)(2n+1)}{24}}}}",
         r"z = \frac{W − [c:W expected if there is no change]}{[d:standard error of W]}"),
    ],
    "One-Way ANOVA": [
        ("F ratio",
         r"F = \frac{\ca{\sum_j n_j(\bar{x}_j - \bar{x})^2} \,/\, \cb{(k-1)}}{\cc{\sum_j \sum_i (x_{ij} - \bar{x}_j)^2} \,/\, \cd{(N-k)}}",
         r"F = \frac{[a:spread of the group means around the grand mean] / [b:(number of groups − 1)]}{[c:spread of scores around their own group's mean] / [d:(total sample size − number of groups)]}"),
        ("Effect size (eta squared)",
         r"\eta^2 = \frac{\ca{SS_{between}}}{\ce{SS_{total}}}",
         r"η² = \frac{[a:variation explained by group]}{[e:total variation in the outcome]}"),
    ],
    "Repeated Measures ANOVA": [
        ("F ratio",
         r"F = \frac{\ca{SS_{conditions}} \,/\, \cb{(k-1)}}{\cc{SS_{error}} \,/\, \cd{(k-1)(n-1)}}",
         r"F = \frac{[a:variation between the condition means] / [b:(number of conditions − 1)]}{[c:leftover variation] / [d:its degrees of freedom]}"),
        ("Removing person-to-person differences",
         r"\cc{SS_{error}} = \ce{SS_{total}} - \ca{SS_{conditions}} - \cf{SS_{subjects}}",
         "[c:leftover variation] = [e:total variation] − [a:variation from conditions] − [f:variation from people simply differing from each other]"),
    ],
    "Factorial ANOVA": [
        ("Model",
         r"y_{ijk} = \mu + \ca{\alpha_i} + \cb{\beta_j} + \cc{(\alpha\beta)_{ij}} + \cd{\varepsilon_{ijk}}",
         "score = overall mean + [a:effect of factor A] + [b:effect of factor B] + [c:extra effect of that particular A-B combination] + [d:random error]"),
        ("F ratio for each effect",
         r"F_{effect} = \frac{\ce{MS_{effect}}}{\cd{MS_{error}}}",
         r"F = \frac{[e:average variation explained by the effect (A, B or A×B)]}{[d:average unexplained variation]}"),
    ],
    "Mixed / Repeated-Measures Factorial ANOVA": [
        ("Model",
         r"y_{ijk} = \mu + \ca{\alpha_i} + \cf{\pi_{k(i)}} + \cb{\beta_j} + \cc{(\alpha\beta)_{ij}} + \cd{\varepsilon_{ijk}}",
         "score = overall mean + [a:between-groups effect] + [f:that person's own baseline] + [b:within-person (time) effect] + [c:group × time interaction] + [d:random error]"),
        ("Between-groups F",
         r"F_{A} = \frac{\ca{MS_{A}}}{\cf{MS_{S(A)}}}",
         r"F = \frac{[a:variation between groups]}{[f:variation between people within each group]}"),
        ("Within-person F",
         r"F_{B} = \frac{\cb{MS_{B}}}{\cd{MS_{B \times S(A)}}}",
         r"F = \frac{[b:variation between time points or conditions]}{[d:how inconsistently people change across them]}"),
    ],
    "ANCOVA": [
        ("Model",
         r"y_{ij} = \mu + \ca{\tau_j} + \cb{\beta}(\cc{x_{ij} - \bar{x}}) + \cd{\varepsilon_{ij}}",
         "score = overall mean + [a:effect of the group] + [b:slope of the covariate] × [c:how far the person's covariate is from average] + [d:random error]"),
        ("Adjusted group mean",
         r"\bar{y}_j^{\,adj} = \bar{y}_j - \cb{b}(\cc{\bar{x}_j - \bar{x}})",
         "adjusted mean = group's raw mean − [b:covariate slope] × [c:how far the group's average covariate is from the overall average]"),
        ("F ratio",
         r"F = \frac{\ca{MS_{groups,\,adj}}}{\cd{MS_{error,\,adj}}}",
         r"F = \frac{[a:variation between the adjusted group means]}{[d:unexplained variation after removing the covariate]}"),
    ],
    "Kruskal-Wallis H Test": [
        ("H statistic",
         r"H = \cc{\frac{12}{N(N+1)}} \sum_{j} \frac{\ca{R_j}^2}{\cb{n_j}} - \cd{3(N+1)}",
         r"H = [c:scaling for the total sample size] × sum over groups of \frac{[a:group's rank total]²}{[b:group size]} − [d:the value that sum gives when groups don't differ]"),
    ],
    "Friedman Test": [
        ("Chi-square statistic",
         r"\chi^2_F = \cc{\frac{12}{n\,k(k+1)}} \sum_{j} \ca{R_j}^2 - \cd{3n(k+1)}",
         "χ² = [c:scaling for the number of people and conditions] × sum over conditions of [a:condition's rank total (ranked within each person)]² − [d:the value expected when conditions don't differ]"),
    ],
    "Aligned Rank Transform (ART) ANOVA": [
        ("Align for one effect (here, factor A)",
         r"y^{\ast}_{ijk} = \cd{(y_{ijk} - \bar{y}_{ij})} + \ca{(\bar{y}_{i\cdot} - \bar{y}_{\cdot\cdot})}",
         "aligned score = [d:the score's residual from its cell mean] + [a:estimated effect of factor A only]"),
        ("Rank, then run the ANOVA",
         r"F_A = \frac{\ca{MS_A}\big(\cb{\mathrm{rank}(y^{\ast})}\big)}{\cd{MS_{error}}\big(\cb{\mathrm{rank}(y^{\ast})}\big)}",
         r"F = \frac{[a:variation for factor A]}{[d:error variation]}, both computed on the [b:ranks of the aligned scores]. Repeat the alignment for every effect."),
    ],
    "Quade's Nonparametric ANCOVA": [
        ("Remove the covariate from the ranks",
         r"\cd{e_{ij}} = \ca{\mathrm{rank}(y_{ij})} - \cb{b}\,\cc{\mathrm{rank}(x_{ij})}",
         "[d:residual] = [a:rank of the outcome] − [b:slope] × [c:rank of the covariate]"),
        ("Compare groups on the residuals",
         r"F = \frac{\ce{\sum_j n_j \bar{e}_j^{\,2}} \,/\, (k-1)}{\cd{\sum_j \sum_i (e_{ij} - \bar{e}_j)^2} \,/\, (N-k)}",
         r"F = \frac{[e:spread of the groups' average residuals] / (groups − 1)}{[d:spread of residuals within groups] / (total sample size − groups)}"),
    ],
    "Chi-Square Test of Independence": [
        ("Chi-square statistic",
         r"\chi^2 = \sum \frac{(\ca{O} - \cb{E})^2}{\cb{E}}",
         r"χ² = sum over every cell of \frac{([a:observed count] − [b:expected count])²}{[b:expected count]}"),
        ("Expected count",
         r"\cb{E} = \frac{\cc{\text{row total}} \times \cd{\text{column total}}}{\ce{N}}",
         r"[b:expected count] = \frac{[c:row total] × [d:column total]}{[e:total sample size]}"),
        ("Effect size (Cramér's V)",
         r"V = \sqrt{\frac{\chi^2}{\ce{N}\,(\min(r, c) - 1)}}",
         r"V = \sqrt{\frac{χ²}{[e:total sample size] × (the smaller of rows or columns − 1)}}"),
    ],
    "McNemar's Test": [
        ("Chi-square statistic",
         r"\chi^2 = \frac{(\ca{b} - \cb{c})^2}{\ca{b} + \cb{c}}",
         r"χ² = \frac{([a:people who switched yes → no] − [b:people who switched no → yes])²}{[a:yes → no] + [b:no → yes]}"),
    ],
    "Cochran's Q Test": [
        ("Q statistic",
         r"Q = \frac{(k-1)\left[k \sum_j \ca{C_j}^2 - \cc{N}^2\right]}{k\,\cc{N} - \sum_i \cb{R_i}^2}",
         r"Q = \frac{(conditions − 1) × (k × sum of [a:'yes' count per condition]² − [c:total 'yes' count]²)}{k × [c:total 'yes' count] − sum of [b:'yes' count per person]²}"),
    ],
    "One-Way MANOVA": [
        ("Wilks' lambda",
         r"\Lambda = \frac{|\cc{\mathbf{E}}|}{|\ca{\mathbf{H}} + \cc{\mathbf{E}}|}",
         r"Λ = \frac{size of [c:the within-group spread across all outcomes]}{size of ([a:between-group spread] + [c:within-group spread])}. Small Λ means the groups differ."),
        ("Pillai's trace",
         r"V = \operatorname{tr}\!\left[\ca{\mathbf{H}}(\ca{\mathbf{H}} + \cc{\mathbf{E}})^{-1}\right]",
         "V = share of the total spread ([a:between groups] + [c:within groups]) that comes from [a:differences between groups]"),
    ],
    "Factorial MANOVA": [
        ("Model",
         r"\mathbf{y}_{ijk} = \boldsymbol{\mu} + \ca{\boldsymbol{\alpha}_i} + \cb{\boldsymbol{\beta}_j} + \cd{(\boldsymbol{\alpha\beta})_{ij}} + \cc{\boldsymbol{\varepsilon}_{ijk}}",
         "outcome vector = means + [a:factor A effect] + [b:factor B effect] + [d:A × B interaction] + [c:random error], with one entry per outcome"),
        ("Wilks' lambda for each effect",
         r"\Lambda_{effect} = \frac{|\cc{\mathbf{E}}|}{|\ce{\mathbf{H}_{effect}} + \cc{\mathbf{E}}|}",
         r"Λ = \frac{[c:within-cell spread]}{[e:spread explained by A, B or A × B] + [c:within-cell spread]}"),
    ],
    "MANCOVA": [
        ("Model",
         r"\mathbf{y}_{ij} = \boldsymbol{\mu} + \ca{\boldsymbol{\tau}_j} + \cb{\mathbf{B}}(\cd{x_{ij} - \bar{x}}) + \cc{\boldsymbol{\varepsilon}_{ij}}",
         "outcome vector = means + [a:group effect] + [b:covariate slopes] × [d:distance of the covariate from average] + [c:random error]"),
        ("Wilks' lambda, adjusted",
         r"\Lambda = \frac{|\cc{\mathbf{E}_{adj}}|}{|\ca{\mathbf{H}_{adj}} + \cc{\mathbf{E}_{adj}}|}",
         r"Λ = \frac{[c:within-group spread after removing the covariate]}{[a:adjusted between-group spread] + [c:adjusted within-group spread]}"),
    ],
    "PERMANOVA (non-parametric MANOVA)": [
        ("Pseudo-F",
         r"F = \frac{\ca{SS_A} \,/\, (a-1)}{\cc{SS_W} \,/\, (N-a)}",
         r"F = \frac{[a:spread between groups] / (groups − 1)}{[c:spread within groups] / (total sample size − groups)}"),
        ("Spread from distances",
         r"\cc{SS_W} = \sum_{groups} \frac{1}{n} \sum_{i<j} \cd{d_{ij}}^2, \qquad \ca{SS_A} = \ce{SS_T} - \cc{SS_W}",
         r"[c:within-group spread] = sum over groups of \frac{sum of squared [d:distances between pairs in the same group]}{group size}; [a:between-group spread] = [e:total spread] − [c:within-group spread]"),
        ("Permutation p-value",
         r"p = \frac{\cf{\#\{F^{\ast} \ge F\}} + 1}{\cb{\text{permutations}} + 1}",
         r"p = \frac{[f:shuffles that gave an F at least as large] + 1}{[b:number of shuffles of the group labels] + 1}"),
    ],
    "Pearson's r Correlation": [
        ("Correlation",
         r"r = \frac{\ca{\sum (x_i - \bar{x})(y_i - \bar{y})}}{\cb{\sqrt{\sum (x_i - \bar{x})^2 \sum (y_i - \bar{y})^2}}}",
         r"r = \frac{[a:how much x and y vary together]}{[b:how much they vary on their own]}"),
        ("Significance test",
         r"t = \frac{r\sqrt{\cc{n-2}}}{\sqrt{1 - r^2}}",
         r"t = \frac{r × \sqrt{[c:sample size − 2]}}{\sqrt{1 − r²}}"),
    ],
    "Spearman's Rank Correlation": [
        ("Rank correlation (no ties)",
         r"\rho = 1 - \frac{6 \sum \ca{d_i}^2}{\cb{n}(\cb{n}^2 - 1)}",
         r"ρ = 1 − \frac{6 × sum of [a:squared differences between each person's two ranks]}{[b:sample size] × (sample size² − 1)}"),
    ],
    "Point-Biserial Correlation": [
        ("Correlation",
         r"r_{pb} = \frac{\ca{M_1 - M_0}}{\cb{s_n}} \sqrt{\cc{p\,q}}",
         r"r = \frac{[a:difference in means between the two categories]}{[b:standard deviation of all scores]} × \sqrt{[c:share in category 1 × share in category 0]}"),
    ],
    "Rank-Biserial Correlation": [
        ("Correlation from U",
         r"r_{rb} = 1 - \frac{2\,\ca{U}}{\cb{n_1 n_2}}",
         r"r = 1 − \frac{2 × [a:Mann-Whitney U]}{[b:number of possible pairs between the groups]}"),
        ("Same thing, read as pairs",
         r"r_{rb} = \cc{P(\text{group 1 wins})} - \cd{P(\text{group 2 wins})}",
         "r = [c:share of pairs where the group 1 score is higher] − [d:share where the group 2 score is higher]"),
    ],
    "Canonical Correlation Analysis": [
        ("Canonical variates",
         r"\ca{U} = \mathbf{a}^\top \mathbf{X}, \qquad \cb{V} = \mathbf{b}^\top \mathbf{Y}",
         "[a:U is a weighted blend of the first set of variables]; [b:V is a weighted blend of the second set]"),
        ("Weights chosen to maximize",
         r"\rho = \operatorname{corr}(\ca{U}, \cb{V}) = \frac{\cc{\mathbf{a}^\top \Sigma_{XY}\, \mathbf{b}}}{\cd{\sqrt{\mathbf{a}^\top \Sigma_{XX}\, \mathbf{a}\;\, \mathbf{b}^\top \Sigma_{YY}\, \mathbf{b}}}}",
         r"ρ = correlation of [a:U] and [b:V] = \frac{[c:how the two blends vary together]}{[d:how much each blend varies on its own]}"),
    ],
    "Simple Linear Regression": [
        ("Prediction line",
         r"\hat{y} = \cb{b_0} + \ca{b_1}\,\cc{x}",
         "predicted outcome = [b:intercept] + [a:slope] × [c:predictor]"),
        ("Slope and intercept",
         r"\ca{b_1} = \frac{\sum (x_i - \bar{x})(y_i - \bar{y})}{\sum (x_i - \bar{x})^2}, \qquad \cb{b_0} = \bar{y} - \ca{b_1}\bar{x}",
         r"[a:slope] = \frac{how x and y vary together}{how x varies alone}; [b:intercept] = mean of y − [a:slope] × mean of x"),
        ("Variance explained",
         r"R^2 = 1 - \frac{\cd{SS_{residual}}}{\ce{SS_{total}}}",
         r"R² = 1 − \frac{[d:prediction errors squared]}{[e:total variation in y]}"),
    ],
    "Multiple Linear Regression": [
        ("Prediction equation",
         r"\hat{y} = \cb{b_0} + \ca{b_1}\cc{x_1} + \ca{b_2}\cc{x_2} + \dots + \ca{b_p}\cc{x_p}",
         "predicted outcome = [b:intercept] + each [a:slope] × its [c:predictor], each slope holding the others constant"),
        ("Least-squares coefficients",
         r"\ca{\mathbf{b}} = (\cc{\mathbf{X}}^\top \cc{\mathbf{X}})^{-1} \cc{\mathbf{X}}^\top \mathbf{y}",
         "[a:coefficients] = the values that make the squared prediction errors as small as possible, given the [c:predictor matrix]"),
        ("Variance explained",
         r"R^2 = 1 - \frac{\cd{SS_{residual}}}{\ce{SS_{total}}}",
         r"R² = 1 − \frac{[d:prediction errors squared]}{[e:total variation in y]}"),
    ],
    "Binary Logistic Regression": [
        ("Log-odds model",
         r"\ln\!\left(\frac{\cd{p}}{1 - \cd{p}}\right) = \cb{b_0} + \ca{b_1}\cc{x_1} + \dots + \ca{b_k}\cc{x_k}",
         "log of the odds of [d:yes] = [b:intercept] + each [a:coefficient] × its [c:predictor]"),
        ("Predicted probability",
         r"\cd{p} = \frac{1}{1 + e^{-(\cb{b_0} + \ca{b_1}\cc{x_1} + \dots)}}",
         r"[d:probability of yes] = \frac{1}{1 + e raised to minus ([b:intercept] + each [a:coefficient] × its [c:predictor])}"),
        ("Odds ratio",
         r"OR = e^{\ca{b_1}}",
         "odds ratio = e raised to the [a:coefficient]: how the odds multiply when that predictor goes up by 1"),
    ],
    "Ordinal Logistic Regression": [
        ("Proportional-odds model",
         r"\ln\!\left(\frac{\cd{P(Y \le j)}}{1 - \cd{P(Y \le j)}}\right) = \cb{\theta_j} - (\ca{b_1}\cc{x_1} + \dots + \ca{b_k}\cc{x_k})",
         "log odds of [d:being at or below level j] = [b:cut-point for level j] − (each [a:coefficient] × its [c:predictor])"),
        ("Odds ratio",
         r"OR = e^{\ca{b_1}}",
         "odds ratio = e raised to the [a:coefficient]: how the odds of a higher category multiply per 1-unit increase, the same at every cut-point"),
    ],
    "Multivariate Multiple Regression": [
        ("Model",
         r"\cd{\mathbf{Y}} = \cc{\mathbf{X}}\ca{\mathbf{B}} + \ce{\mathbf{E}}",
         "[d:outcomes, one column each] = [c:predictors] × [a:coefficients, one column per outcome] + [e:errors]"),
        ("Coefficients",
         r"\ca{\hat{\mathbf{B}}} = (\cc{\mathbf{X}}^\top \cc{\mathbf{X}})^{-1} \cc{\mathbf{X}}^\top \cd{\mathbf{Y}}",
         "[a:coefficients] = the least-squares fit of every [d:outcome] on the [c:predictors] at once; the multivariate tests then use the errors' shared covariance"),
    ],
    "Linear Mixed-Effects Model": [
        ("Model",
         r"\mathbf{y} = \cc{\mathbf{X}}\ca{\boldsymbol{\beta}} + \cd{\mathbf{Z}}\cb{\mathbf{u}} + \ce{\boldsymbol{\varepsilon}}",
         "outcome = [c:fixed predictors (group, time, covariate)] × [a:fixed effects] + [d:which person each row belongs to] × [b:random effects] + [e:residual error]"),
        ("Example: repeated measures with a covariate",
         r"y_{ti} = \ca{\beta_0} + \ca{\beta_1}\,\text{group}_i + \ca{\beta_2}\,\text{time}_t + \ca{\beta_3}\,\text{baseline}_i + \cb{u_{0i}} + \ce{\varepsilon_{ti}}",
         "score at time t for person i = [a:fixed intercept and effects of group, time and baseline] + [b:that person's own offset] + [e:error]"),
        ("Random effects are assumed normal",
         r"\cb{\mathbf{u}} \sim N(0, \mathbf{G}), \qquad \ce{\boldsymbol{\varepsilon}} \sim N(0, \sigma^2 \mathbf{I})",
         "[b:person offsets] vary around zero; [e:errors] vary around zero with constant variance"),
    ],
    "Hierarchical Linear Model (HLM)": [
        ("Level 1 (individuals)",
         r"y_{ij} = \cb{\beta_{0j}} + \cc{\beta_{1j}}\,x_{ij} + \ce{r_{ij}}",
         "student i's score in school j = [b:that school's intercept] + [c:that school's slope] × predictor + [e:individual error]"),
        ("Level 2 (groups)",
         r"\cb{\beta_{0j}} = \ca{\gamma_{00}} + \ca{\gamma_{01}}\,w_j + \cd{u_{0j}}",
         "[b:school's intercept] = [a:overall intercept and effect of a school-level predictor] + [d:that school's random deviation]"),
        ("Intraclass correlation",
         r"ICC = \frac{\cd{\tau_{00}}}{\cd{\tau_{00}} + \ce{\sigma^2}}",
         r"ICC = \frac{[d:variance between groups]}{[d:between-group variance] + [e:within-group variance]}"),
    ],
}
if set(TEST_EQUATIONS) != {t.name for t in TESTS}:
    raise ValueError(f"TEST_EQUATIONS and TESTS disagree: {set(TEST_EQUATIONS) ^ {t.name for t in TESTS}}")


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
        if a.infer:
            lines.append(f"    {a.infer}")
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