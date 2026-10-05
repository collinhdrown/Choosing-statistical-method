"""
quiz_bank.py — questions for the Quiz Yourself tab.

Three quizzes, served as-is by server.py's /api/quizzes. Nothing here decides which test fits a
study: every "Pick the Method" answer carries the stat_engine answers that describe its scenario,
and validate() checks at import that stat_engine recommends exactly that test, so the quiz can't
drift from the Method Matcher.
"""
from __future__ import annotations

import stat_engine as se

SCALES = ["Nominal", "Ordinal", "Interval", "Ratio"]

# (variable, answer, why)
SCALE_QUESTIONS: list[tuple[str, str, str]] = [
    ("A patient's blood type (A, B, AB or O)", "Nominal",
     "The types are names with no order: AB isn't more or less than O."),
    ("A runner's finishing place in a race (1st, 2nd, 3rd, ...)", "Ordinal",
     "Places are ranked, but the gap between 1st and 2nd isn't the same as between 2nd and 3rd."),
    ("Outdoor temperature in degrees Celsius", "Interval",
     "Equal steps mean equal differences, but 0 °C isn't 'no temperature', so 20 °C isn't twice as hot as 10 °C."),
    ("Reaction time in milliseconds", "Ratio",
     "Equal steps and a true zero: 400 ms really is twice as long as 200 ms."),
    ("Agreement with a statement on a 5-point scale from Strongly disagree to Strongly agree", "Ordinal",
     "The answers are ordered, but nothing guarantees the steps between them are equal."),
    ("Annual household income in dollars", "Ratio",
     "$0 means no income, so ratios make sense: $80,000 is twice $40,000."),
    ("A participant's home zip code", "Nominal",
     "Zip codes are numbers used as labels; averaging them or ranking them means nothing."),
    ("The calendar year a participant was born", "Interval",
     "Years are evenly spaced, but the calendar's starting point is arbitrary, not an absence of time."),
    ("Number of siblings a person has", "Ratio",
     "It's a count with a true zero: someone with 4 siblings has twice as many as someone with 2."),
    ("Highest education completed (high school, bachelor's, master's, doctorate)", "Ordinal",
     "The levels have a clear order, but the distance between them isn't a fixed amount."),
]

# (scenario, answer, distractors, stat_engine answers for the scenario, why)
METHOD_QUESTIONS: list[tuple[str, str, list[str], dict, str]] = [
    ("A researcher randomly gives 60 adults either caffeine or a placebo, then measures each person's "
     "reaction time once. Reaction times are roughly normal.",
     "Independent Samples t-test",
     ["Paired Samples t-test", "One-Way ANOVA", "Pearson's r Correlation"],
     dict(purpose="difference", dv_count="one", iv_count="one", iv_type="nominal", covariates="no",
          nested="no", groups="two", pairing="independent", dv_type="continuous", normal="yes"),
     "Two separate groups compared on one normally distributed continuous outcome."),
    ("A clinic measures the blood pressure of 25 patients before and again after an 8-week diet "
     "program. The differences are roughly normal.",
     "Paired Samples t-test",
     ["Independent Samples t-test", "Repeated Measures ANOVA", "Chi-Square Test of Independence"],
     dict(purpose="difference", dv_count="one", iv_count="one", iv_type="nominal", covariates="no",
          nested="no", groups="two", pairing="repeated", dv_type="continuous", normal="yes"),
     "The same people are measured twice, so the two sets of scores are paired."),
    ("A school compares final exam scores of students taught with three different methods: lecture, "
     "flipped classroom and online. Each student is in one class, and scores are roughly normal.",
     "One-Way ANOVA",
     ["Independent Samples t-test", "Factorial ANOVA", "Kruskal-Wallis H Test"],
     dict(purpose="difference", dv_count="one", iv_count="one", iv_type="nominal", covariates="no",
          nested="no", groups="three_plus", pairing="independent", dv_type="continuous", normal="yes"),
     "One grouping variable with three separate groups and a normal continuous outcome."),
    ("A survey records whether each respondent smokes (yes or no) and whether they exercise weekly "
     "(yes or no). The researcher wants to know if the two are related.",
     "Chi-Square Test of Independence",
     ["Pearson's r Correlation", "Independent Samples t-test", "McNemar's Test"],
     dict(purpose="difference", dv_count="one", iv_count="one", iv_type="nominal", covariates="no",
          nested="no", groups="two", pairing="independent", dv_type="nominal"),
     "Both variables are categories from separate people, so you compare counts in a table."),
    ("A researcher records how many hours 200 college students sleep per night and their GPA, and asks "
     "whether the two move together. Both are roughly normal.",
     "Pearson's r Correlation",
     ["Spearman's Rank Correlation", "Simple Linear Regression", "Independent Samples t-test"],
     dict(purpose="association", dv_count="one", iv_count="one", iv_type="continuous",
          nested="no", dv_type="continuous", normal="yes"),
     "Two normally distributed continuous variables and a question about how strongly they're related."),
    ("A realtor wants to predict a house's sale price from its square footage alone.",
     "Simple Linear Regression",
     ["Multiple Linear Regression", "Pearson's r Correlation", "Binary Logistic Regression"],
     dict(purpose="prediction", dv_count="one", iv_count="one", iv_type="continuous",
          nested="no", dv_type="continuous"),
     "The goal is prediction, from one continuous predictor to one continuous outcome."),
    ("An HR analyst predicts employees' salaries from years of experience, years of education and "
     "weekly hours worked.",
     "Multiple Linear Regression",
     ["Simple Linear Regression", "Binary Logistic Regression", "Factorial ANOVA"],
     dict(purpose="prediction", dv_count="one", iv_count="many", iv_type="continuous",
          nested="no", dv_type="continuous"),
     "Several predictors and one continuous outcome to predict."),
    ("A hospital wants to predict whether a patient is readmitted within 30 days (yes or no) from their "
     "age, BMI and number of medications.",
     "Binary Logistic Regression",
     ["Multiple Linear Regression", "Chi-Square Test of Independence", "Ordinal Logistic Regression"],
     dict(purpose="prediction", dv_count="one", iv_count="many", iv_type="continuous",
          nested="no", dv_type="nominal"),
     "The outcome has exactly two categories, so a linear model on it won't work."),
    ("Customers at two different stores rate their satisfaction from 1 (very unhappy) to 5 (very "
     "happy). The researcher compares the two stores.",
     "Mann-Whitney U Test",
     ["Independent Samples t-test", "Wilcoxon Signed-Rank Test", "Spearman's Rank Correlation"],
     dict(purpose="difference", dv_count="one", iv_count="one", iv_type="nominal", covariates="no",
          nested="no", groups="two", pairing="independent", dv_type="ordinal"),
     "Two separate groups on a ranked (ordinal) outcome, so you compare ranks rather than means."),
    ("The same 30 participants take a memory test after 4, 6 and 8 hours of sleep, on three different "
     "nights. Scores are roughly normal.",
     "Repeated Measures ANOVA",
     ["One-Way ANOVA", "Paired Samples t-test", "Friedman Test"],
     dict(purpose="difference", dv_count="one", iv_count="one", iv_type="nominal", covariates="no",
          nested="no", groups="three_plus", pairing="repeated", dv_type="continuous", normal="yes"),
     "Three conditions, each experienced by the same people, on a normal continuous outcome."),
]

# Each scenario has several parts: (prompt, options, answer, why). Options keep their order.
VARIABLE_QUESTIONS: list[tuple[str, list[tuple[str, list[str], str, str]]]] = [
    ("A researcher randomly assigns 90 adults to drink water, regular coffee or decaf coffee, then "
     "measures how many words per minute each person types.", [
        ("What is the independent variable?",
         ["Words per minute", "Type of drink", "The 90 adults", "Typing ability"], "Type of drink",
         "The drink is what the researcher sets; typing speed is what they measure."),
        ("What is the dependent variable?",
         ["Type of drink", "Caffeine", "Words per minute", "Age"], "Words per minute",
         "Typing speed is the outcome that might change depending on the drink."),
        ("How many levels does the independent variable have?",
         ["1", "2", "3", "90"], "3",
         "Water, regular coffee and decaf coffee."),
        ("Is the independent variable between-subjects or within-subjects?",
         ["Between-subjects", "Within-subjects", "Mixed"], "Between-subjects",
         "Each person drinks only one of the three, so the groups are different people."),
    ]),
    ("Forty students take a vocabulary test before and again after a six-week reading program.", [
        ("What is the independent variable?",
         ["Vocabulary score", "Time (before vs. after the program)", "Number of students", "Reading speed"],
         "Time (before vs. after the program)",
         "The comparison is between the two testing times around the program."),
        ("What is the dependent variable?",
         ["Vocabulary score", "The reading program", "Six weeks", "Time"], "Vocabulary score",
         "The test score is what's measured at each time."),
        ("How many levels does the independent variable have?",
         ["1", "2", "6", "40"], "2",
         "Before and after."),
        ("Is the independent variable between-subjects or within-subjects?",
         ["Between-subjects", "Within-subjects", "Mixed"], "Within-subjects",
         "Every student is tested at both times."),
    ]),
    ("A botanist grows 60 plants under one of three fertilizers (none, organic or synthetic) and one of "
     "two watering schedules (daily or weekly), then measures each plant's height after eight weeks.", [
        ("How many independent variables are there?",
         ["1", "2", "3", "6"], "2",
         "Fertilizer and watering schedule."),
        ("How many levels does each independent variable have?",
         ["3 and 2", "2 and 2", "3 and 3", "6 and 1"], "3 and 2",
         "Fertilizer has three levels and watering has two, a 3 × 2 design."),
        ("How many different conditions (cells) are in the design?",
         ["2", "5", "6", "60"], "6",
         "Every fertilizer is paired with every watering schedule: 3 × 2 = 6."),
        ("What is the dependent variable?",
         ["Fertilizer", "Watering schedule", "Plant height", "Eight weeks"], "Plant height",
         "Height is measured; fertilizer and watering are set by the botanist."),
    ]),
    ("In a sleep study, each of 24 participants spends one night each at 4, 6 and 8 hours of sleep. The "
     "next morning the researcher records their reaction time and the number of errors on a task.", [
        ("What is the independent variable?",
         ["Reaction time", "Hours of sleep", "Number of errors", "The task"], "Hours of sleep",
         "Sleep duration is what the researcher controls."),
        ("How many dependent variables are there?",
         ["1", "2", "3", "24"], "2",
         "Reaction time and number of errors are both outcomes."),
        ("How many levels does the independent variable have?",
         ["2", "3", "8", "24"], "3",
         "4, 6 and 8 hours."),
        ("Is the independent variable between-subjects or within-subjects?",
         ["Between-subjects", "Within-subjects", "Mixed"], "Within-subjects",
         "Each participant experiences all three sleep durations."),
    ]),
    ("Patients with depression are randomly assigned to therapy or a waitlist. Every patient's depression "
     "score is measured before treatment, right after, and three months later.", [
        ("Which independent variable is within-subjects?",
         ["Group (therapy vs. waitlist)", "Time of measurement", "Depression score", "Neither"],
         "Time of measurement",
         "Every patient is measured at all three times, but each is in only one group."),
        ("How many levels does the time variable have?",
         ["2", "3", "4", "6"], "3",
         "Before, right after, and three months later."),
        ("What is the dependent variable?",
         ["Therapy", "Depression score", "Time", "Waitlist"], "Depression score",
         "The score is what's measured at each time point."),
        ("What kind of design is this overall?",
         ["Between-subjects", "Within-subjects", "Mixed", "Correlational"], "Mixed",
         "It has one between-subjects factor (group) and one within-subjects factor (time)."),
    ]),
]


def validate() -> None:
    names = {t.name for t in se.TESTS}
    assert len(SCALE_QUESTIONS) == 10 and len(METHOD_QUESTIONS) == 10 and len(VARIABLE_QUESTIONS) == 5
    for variable, answer, _ in SCALE_QUESTIONS:
        assert answer in SCALES, variable
    for scenario, answer, distractors, answers, _ in METHOD_QUESTIONS:
        options = [answer, *distractors]
        assert len(set(options)) == 4 and set(options) <= names, (scenario, set(options) - names)
        result = se.recommend(se.canonicalize(answers))
        assert result.get("test") == answer, (scenario, result)
    for scenario, parts in VARIABLE_QUESTIONS:
        for prompt, options, answer, _ in parts:
            assert answer in options and len(set(options)) == len(options), (scenario, prompt)


validate()


def quizzes() -> list[dict]:
    """The three quizzes in the shape the page draws them."""
    return [
        {
            "slug": "scales",
            "title": "Identify the Measurement Scale",
            "blurb": "Ten variables. Is each one nominal, ordinal, interval or ratio?",
            "kind": "single",
            "questions": [{"prompt": v, "options": SCALES, "answer": a, "why": w}
                          for v, a, w in SCALE_QUESTIONS],
        },
        {
            "slug": "methods",
            "title": "Pick the Method",
            "blurb": "Ten research scenarios. Choose the best test out of four.",
            "kind": "single",
            "shuffle_options": True,
            "questions": [{"prompt": s, "options": [a, *d], "answer": a, "why": w, "test": a}
                          for s, a, d, _, w in METHOD_QUESTIONS],
        },
        {
            "slug": "variables",
            "title": "Variables and Groups",
            "blurb": "Five studies. Find the IVs, DVs, levels and design in each.",
            "kind": "parts",
            "questions": [{"prompt": s, "parts": [{"prompt": p, "options": o, "answer": a, "why": w}
                                                  for p, o, a, w in parts]}
                          for s, parts in VARIABLE_QUESTIONS],
        },
    ]
