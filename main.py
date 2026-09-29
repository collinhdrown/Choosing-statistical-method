"""
main.py — CLI entry point and shared OpenAI helpers for the Sage Stats Advisor.

Both this CLI and app.py (the Streamlit UI) import extract_variables_from_text() and
generate_conversational_response() from here. All statistical logic — the question list,
the test catalog, and which question to ask next — lives in stat_engine.py. This file only
talks to the LLM and drives the command-line loop.
"""
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

import stat_engine as se

# ========================================================
# 1. CREDENTIALS
# ========================================================
script_directory = os.path.dirname(os.path.abspath(__file__))
env_file_path = os.path.join(script_directory, ".env")
load_dotenv(env_file_path)

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print(f"⚠️ Key Configuration Error: Could not read OPENAI_API_KEY from absolute path: {env_file_path}")
    sys.exit(1)

client = OpenAI(api_key=api_key)

# Pydantic schema built from stat_engine.ATTRIBUTES: one Optional[Literal[...]] field per
# question, so the LLM can only ever return vocabulary the engine understands.
ExtractedState = se.extraction_model()


# ========================================================
# 2. LLM HELPERS  (imported by both main.py and app.py)
# ========================================================
def extract_variables_from_text(conversation_history: str, current_state: dict) -> dict:
    """Ask the LLM to fill in whichever stat_engine attributes the conversation already answers.

    Only fields with a valid enum value are kept (stat_engine.merge_state), and `False`/"no"-type
    answers are preserved rather than dropped, unlike the old truthiness-based merge.
    """
    response = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": se.extraction_prompt(current_state)},
            {"role": "user", "content": f"Conversation Transcript:\n{conversation_history}"},
        ],
        response_format=ExtractedState,
    )
    extracted = response.choices[0].message.parsed.model_dump()
    return se.merge_state(current_state, extracted)


def generate_conversational_response(missing_key: str, current_state: dict) -> str:
    """Turn the next unanswered stat_engine.Attribute into a natural, two-sentence question."""
    info = se.question_for(missing_key)
    prompt = (
        "Ask the user this exact question in a natural, professional way, immediately followed "
        "by the example given below. Exactly 2 sentences total. No greetings, no extra commentary, "
        "and don't mention internal field names.\n\n"
        f"QUESTION: {info['question']}\n"
        f"EXAMPLE: {info['hint'] or 'Give a brief, concrete example if it helps.'}"
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


# ========================================================
# 3. CLI LOOP
# ========================================================
def run_consultation():
    print("====================================================")
    print("🎓 SAGE STATS ADVISOR: INITIALIZED")
    print("Describe your research project, variables, or data setup below.")
    print("Type 'exit' to quit at any point.")
    print("====================================================\n")

    state: dict = {}
    transcript = ""

    while True:
        user_input = input("You: ")
        if user_input.strip().lower() == "exit":
            print("\nGoodbye!")
            break

        transcript += f"\nUser: {user_input}"
        print("\n[Analyzing data properties...]")
        state = extract_variables_from_text(transcript, state)

        # Canonicalize before asking the engine anything: drops any answer that's out of
        # order or that a later answer has made impossible, so the CLI reaches the same
        # verdict the Streamlit form would from identical raw answers.
        canon_state = se.canonicalize(state)
        print(f"📊 Running State Ledger: {canon_state}")

        result = se.recommend(canon_state)

        if result["status"] == "complete":
            note = f" — {result['note']}" if result.get("note") else ""
            print(f"\n🎯 RECOMMENDED STATISTICAL METHOD: {result['test']}{note}\n")
            break

        if result["status"] == "no_match":
            print(
                "\n⚠️ Those answers don't match any test in the catalog. "
                f"Try revisiting: {', '.join(result['conflicts']) or 'your last answer'}.\n"
            )
            continue

        if result["status"] == "ambiguous":
            print(
                f"\nSeveral tests still fit equally well: {', '.join(result['tests'])}. "
                "Can you give a bit more detail about your study?\n"
            )
            continue

        # result["status"] == "incomplete"
        ai_question = generate_conversational_response(result["ask_for"], canon_state)
        print(f"\nAdvisor: {ai_question}\n")
        transcript += f"\nAdvisor: {ai_question}"


if __name__ == "__main__":
    run_consultation()