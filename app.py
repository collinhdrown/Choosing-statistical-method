"""
app.py — Streamlit UI for the Sage Stats Advisor.

The left panel's dropdowns, the right panel's active/eliminated test bubbles, and the chat
extraction all read from stat_engine.py — nothing here decides which test applies to which
answers. Adding a test or a question to stat_engine.py shows up here automatically; this file
never needs to change for that.
"""
import streamlit as st

import stat_engine as se
from main import extract_variables_from_text, generate_conversational_response

# ========================================================
# 1. PAGE THEME
# ========================================================
st.set_page_config(page_title="StatTest Matcher", layout="wide")

st.markdown(
    """
    <style>
        .stApp { background-color: #0A1128; color: #E2E8F0; }
        h1, h2, h3, h4, p, label, .stMarkdown { color: #E2E8F0 !important; }
        div[data-baseweb="select"] > div, div[role="radiogroup"] label {
            background-color: #111E46 !important; color: #E2E8F0 !important; border-color: #1E293B !important;
        }
        div[data-testid="stHeader"] { background-color: rgba(10, 17, 40, 0); }
        .stat-bubble {
            padding: 15px; border-radius: 12px; text-align: center; margin: 8px; font-weight: bold;
            transition: all 0.3s ease; box-shadow: 2px 2px 10px rgba(0,0,0,0.3);
        }
        .active-bubble { background-color: #1E3A8A; border: 2px solid #3B82F6; color: #F8FAFC; }
        .eliminated-bubble { background-color: #0F172A; border: 2px dashed #334155; color: #64748B; opacity: 0.35; }
        button[kind="secondary"] { background-color: #1E293B !important; color: #E2E8F0 !important; border: 1px solid #475569 !important; }
        textarea[data-testid="stChatInputTextArea"] { color: #0A1128 !important; caret-color: #0A1128 !important; }
        div[data-testid="stChatInput"] { background-color: #F8FAFC !important; border: 1px solid #CBD5E1 !important; border-radius: 8px; }
    </style>
    """,
    unsafe_allow_html=True,
)

UNSELECTED = "— Select —"


def reset_application_state():
    st.session_state.answers = {}          # {attribute_key: value}, engine vocabulary only
    st.session_state.chat_transcript = []
    st.session_state.run_counter = st.session_state.get("run_counter", 0) + 1


if "answers" not in st.session_state:
    st.session_state.run_counter = 0
    reset_application_state()

st.title("StatTest Matcher")
st.write("Adjust settings on the left panel or use the chat tool below to narrow down your study parameters.")

col_left, col_right = st.columns([1, 2])

# ========================================================
# 2. LEFT PANEL — dynamic form, driven entirely by stat_engine
# ========================================================
# Walk the SAME question order the engine itself would ask in. Each iteration:
#   - asks the engine what the next relevant question is, given answers gathered so far
#   - shows a dropdown for it, seeded with any previously saved answer that's still valid
#   - stops as soon as a question is left on "— Select —", so later questions stay hidden
#     until earlier ones are answered (matches the old progressive-reveal UX)
path_state: dict = {}
with col_left:
    for _ in range(len(se.ATTRIBUTES) + 1):
        result = se.recommend(path_state)
        if result["status"] != "incomplete":
            break

        key = result["ask_for"]
        attr = se.ATTR[key]
        valid = se.valid_options(attr, path_state)          # options that aren't logically impossible here
        labels = [UNSELECTED] + list(valid.values())
        value_by_label = {UNSELECTED: None, **{lbl: val for val, lbl in valid.items()}}
        label_by_value = {val: lbl for val, lbl in valid.items()}

        saved_value = st.session_state.answers.get(key)
        default_label = label_by_value.get(saved_value, UNSELECTED)

        chosen_label = st.selectbox(
            attr.question,
            labels,
            index=labels.index(default_label),
            help=attr.hint or None,
            key=f"{key}_key_{st.session_state.run_counter}",
        )
        chosen_value = value_by_label[chosen_label]

        if chosen_value is None:
            st.session_state.answers.pop(key, None)
            break                                            # don't reveal later questions yet

        path_state[key] = chosen_value
        st.session_state.answers[key] = chosen_value

    st.markdown(" ")
    st.button("Reset Workspace", use_container_width=True, on_click=reset_application_state)

# path_state now holds exactly the answers on the engine's current path — anything the user
# answered earlier that's no longer reachable (e.g. they changed "Goal" back) is naturally
# excluded, since this loop rebuilds it from scratch each render.
final_result = se.recommend(path_state)

# ========================================================
# 3. RIGHT PANEL — active/eliminated test bubbles + chat
# ========================================================
with col_right:
    active_names = {t.name for t in se.candidates(path_state)}

    grid_cols = st.columns(3)
    for idx, test in enumerate(se.TESTS):
        current_col = grid_cols[idx % 3]
        css_class = "active-bubble" if test.name in active_names else "eliminated-bubble"
        current_col.markdown(f'<div class="stat-bubble {css_class}">{test.name}</div>', unsafe_allow_html=True)

    if final_result["status"] == "complete":
        note = f"  \n*{final_result['note']}*" if final_result.get("note") else ""
        st.success(f"Optimal Recommendation: **{final_result['test']}**{note}")
    elif final_result["status"] == "no_match":
        st.error(
            "These answers don't match any test in the catalog. "
            f"Try revisiting: {', '.join(final_result['conflicts']) or 'your last answer'}."
        )
    elif final_result["status"] == "ambiguous":
        st.warning(f"Still tied between: {', '.join(final_result['tests'])}. Add more detail below.")

    st.markdown("---")

    for msg in st.session_state.chat_transcript:
        if msg["role"] == "user":
            st.markdown(f"**You:** {msg['content']}")
        else:
            st.markdown(f"**Advisor:** {msg['content']}")

    user_query = st.chat_input("Describe your research questions, variable setups, or data shapes...")
    if user_query:
        st.session_state.chat_transcript.append({"role": "user", "content": user_query})
        with st.spinner("Analyzing variables context..."):
            history_text = "".join(f"\n{m['role']}: {m['content']}" for m in st.session_state.chat_transcript)
            # Extract against the full saved state (not just this path) so the LLM sees
            # everything the user has told it so far, including earlier form selections.
            st.session_state.answers = extract_variables_from_text(history_text, st.session_state.answers)

            # Canonicalize before asking the engine anything: this is the same order-consistency
            # check the form's dropdown loop applies, so chat and the manual form can never
            # reach a different verdict from the same underlying answers.
            canon_state = se.canonicalize(st.session_state.answers)
            post_eval = se.recommend(canon_state)
            if post_eval["status"] == "complete":
                note = f" — {post_eval['note']}" if post_eval.get("note") else ""
                ai_reply = f"Based on what you've told me, I'd recommend: {post_eval['test']}{note}"
            elif post_eval["status"] == "no_match":
                ai_reply = (
                    "Some of those answers conflict with each other — could you double-check "
                    f"{', '.join(post_eval['conflicts']) or 'your last point'}?"
                )
            elif post_eval["status"] == "ambiguous":
                ai_reply = f"That narrows it down to {', '.join(post_eval['tests'])}. Can you tell me more?"
            else:
                ai_reply = generate_conversational_response(post_eval["ask_for"], canon_state)

            st.session_state.chat_transcript.append({"role": "assistant", "content": ai_reply})
        st.rerun()