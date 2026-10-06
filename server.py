"""
server.py — FastAPI web app for the Sage Stats Advisor.

Serves the single-page UI in static/ and a small JSON API around it. Like app.py, nothing
here decides which test applies to which answers: every answer goes through stat_engine.py,
and the chat endpoint reuses the OpenAI helpers from main.py.

Run from the repository root:
    uvicorn server:app --reload
then open http://127.0.0.1:8000
"""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import quiz_bank
import stat_engine as se

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = FastAPI(title="Method Matcher")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ========================================================
# 1. VIEW — everything the page draws for a set of answers
# ========================================================
def build_view(answers: dict) -> dict:
    """Canonicalize the answers and describe the resulting state for the UI.

    `eliminated` replays the canonical path one answer at a time, so each ruled-out test is
    tagged with the question whose answer removed it.
    """
    canon = se.canonicalize(answers)
    result = se.recommend(canon)

    eliminated: dict[str, str] = {}
    replay: dict = {}
    for key, value in canon.items():
        before = {t.name for t in se.candidates(replay)}
        replay[key] = value
        after = {t.name for t in se.candidates(replay)}
        for name in before - after:
            eliminated[name] = se.ATTR[key].short

    view = {
        "answers": canon,
        "path": [
            {"key": k, "short": se.ATTR[k].short, "label": se.ATTR[k].options[v]}
            for k, v in canon.items()
        ],
        "result": result,
        "active": [t.name for t in se.candidates(canon)],
        "eliminated": eliminated,
        "question": None,
        "what_ifs": [],
    }

    if result["status"] == "incomplete":
        attr = se.ATTR[result["ask_for"]]
        view["question"] = {
            "key": attr.key,
            "short": attr.short,
            "question": attr.question,
            "hint": attr.hint,
            "options": [
                {
                    "value": value,
                    "label": label,
                    "remaining": [t.name for t in se.candidates({**canon, attr.key: value})],
                }
                for value, label in se.valid_options(attr, canon).items()
            ],
        }
    elif result["status"] == "complete":
        view["what_ifs"] = what_ifs(canon, result["test"])

    return view


def what_ifs(canon: dict, current: str, limit: int = 4) -> list[dict]:
    """Single-answer changes that lead to a different complete recommendation.

    Later answers are checked first (they're the ones a user most often second-guesses, like
    normality), and every other answer is kept wherever it still applies after the change.
    """
    seen = {current}
    out = []
    for key in reversed(list(canon)):
        attr = se.ATTR[key]
        for value, label in se.valid_options(attr, canon).items():
            if value == canon[key]:
                continue
            trial = se.canonicalize({**canon, key: value})
            result = se.recommend(trial)
            if result["status"] == "complete" and result["test"] not in seen:
                seen.add(result["test"])
                out.append({"short": attr.short, "label": label, "test": result["test"], "answers": trial})
                if len(out) >= limit:
                    return out
    return out


# ========================================================
# 2. ROUTES
# ========================================================
class StateRequest(BaseModel):
    answers: dict[str, str] = {}


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    transcript: list[ChatMessage] = []
    answers: dict[str, str] = {}


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/catalog")
def catalog():
    """Everything the hover cards and the Explore tab show for each test."""
    family_of = {name: fam for fam, _, names in se.TEST_FAMILIES for name in names}
    return {
        "families": [{"name": fam, "blurb": blurb, "tests": names} for fam, blurb, names in se.TEST_FAMILIES],
        "tests": [
            {
                "name": t.name,
                "note": t.note,
                "summary": se.TEST_INFO[t.name][0],
                "example": se.TEST_INFO[t.name][1],
                "requirements": [{"short": short, "values": values} for short, values in se.requirements(t)],
                "family": family_of[t.name],
                "equations": [{"label": label, "math": math, "words": words}
                              for label, math, words in se.TEST_EQUATIONS[t.name]],
            }
            for t in se.TESTS
        ],
    }


@app.post("/api/state")
def state(req: StateRequest):
    return build_view(req.answers)


@app.get("/api/quizzes")
def quizzes():
    """The Quiz Yourself tab's questions; quiz_bank checks its answers against stat_engine."""
    return quiz_bank.quizzes()


def _advisor():
    """Import main.py's OpenAI helpers on first use.

    main.py exits when OPENAI_API_KEY is missing, so importing it lazily lets the question
    flow work without a key; only the description reader needs one.
    """
    try:
        import main
    except SystemExit:
        raise HTTPException(
            status_code=503,
            detail="The advisor needs an OPENAI_API_KEY environment variable (set it in your "
                   "host's environment settings, or in a .env file beside main.py when running "
                   "locally). You can still answer the questions directly.",
        )
    return main


@app.post("/api/chat")
def chat(req: ChatRequest):
    advisor = _advisor()
    transcript = [*req.transcript, ChatMessage(role="user", content=req.message)]
    history = "".join(f"\n{m.role}: {m.content}" for m in transcript)

    # Same flow as app.py: merge into the full raw answers (so facts mentioned ahead of their
    # question aren't lost), then canonicalize before asking the engine anything.
    answers = advisor.extract_variables_from_text(history, req.answers)
    view = build_view(answers)
    result = view["result"]

    help_text = None
    if result["status"] == "complete":
        note = f" ({result['note']})" if result.get("note") else ""
        reply = f"Based on what you've told me, I'd recommend the {result['test']}{note}."
    elif result["status"] == "no_match":
        conflicts = ", ".join(se.ATTR[k].short for k in result["conflicts"]) or "your last point"
        reply = f"Some of those answers conflict with each other. Could you double-check {conflicts}?"
    elif result["status"] == "ambiguous":
        reply = f"That narrows it down to {', '.join(result['tests'])}. Can you tell me more?"
    else:
        reply = advisor.generate_conversational_response(result["ask_for"], view["answers"])
        help_text = se.ATTR[result["ask_for"]].hint or None

    return {
        "reply": reply,
        "help": help_text,      # shown behind a "?" icon on the reply
        "answers": answers,
        "from_text": [k for k, v in answers.items() if req.answers.get(k) != v],
        "view": view,
    }
