"""
app.py — Streamlit UI for the Sage Stats Advisor.

The left panel's dropdowns, the right panel's active/eliminated test bubbles, and the chat
extraction all read from stat_engine.py — nothing here decides which test applies to which
answers. Adding a test or a question to stat_engine.py shows up here automatically; this file
never needs to change for that.
"""
import json

import streamlit as st
import streamlit.components.v1 as components

import stat_engine as se
from main import extract_variables_from_text, generate_conversational_response

# ========================================================
# 1. PAGE THEME — olive green / cream / charcoal / white
# ========================================================
st.set_page_config(page_title="StatTest Matcher", layout="wide")

OLIVE = "#6B7A3A"        # primary accent — active bubbles, headers
OLIVE_DARK = "#4E5A2A"   # borders / hover on olive elements
CREAM = "#F5F1E6"        # page background
CHARCOAL = "#2E2E2C"     # body text, active-bubble text
WHITE = "#FFFFFF"        # cards, inputs

# Internal coordinate system the circle-packing layout is computed in. The SVG scales this
# to whatever width Streamlit actually renders via viewBox, so the layout math never has to
# read the real DOM size — which is unreliable inside a components.html iframe on first paint.
PACK_WIDTH = 1000
PACK_HEIGHT = 780

st.markdown(
    f"""
    <style>
        .stApp {{ background-color: {CREAM}; color: {CHARCOAL}; }}
        h1, h2, h3, h4, p, label, .stMarkdown {{ color: {CHARCOAL} !important; }}
        div[data-baseweb="select"] > div, div[role="radiogroup"] label {{
            background-color: {WHITE} !important; color: {CHARCOAL} !important; border-color: {OLIVE_DARK} !important;
        }}
        div[data-testid="stHeader"] {{ background-color: rgba(245, 241, 230, 0); }}
        /* Pull the whole app up and tighten the gap between the title and what follows it,
           so the visual sits right under the title instead of floating further down the
           page, while leaving enough top clearance that the title doesn't sit underneath
           Streamlit's fixed header bar (which is ~2.9rem tall and overlaps the content area
           below padding-top: ~2.9rem). These are common Streamlit structural hooks, not
           guaranteed stable across every Streamlit version -- if your installed version uses
           different internal class/testid names, inspect the element in your browser and
           adjust the selector. */
        .block-container {{ padding-top: 3rem !important; }}
        div[data-testid="stVerticalBlock"] {{ gap: 0.5rem !important; }}
        h1 {{ margin-bottom: 0.2rem !important; }}
        button[kind="secondary"] {{ background-color: {WHITE} !important; color: {CHARCOAL} !important; border: 1px solid {OLIVE_DARK} !important; }}
        button[kind="primary"] {{ background-color: {OLIVE} !important; border-color: {OLIVE_DARK} !important; }}
        textarea[data-testid="stChatInputTextArea"] {{ color: {CHARCOAL} !important; caret-color: {CHARCOAL} !important; }}
        div[data-testid="stChatInput"] {{ background-color: {WHITE} !important; border: 1px solid #C9C4B3 !important; border-radius: 8px; }}
        div[data-testid="stAlert"] {{ background-color: {WHITE} !important; border: 1px solid {OLIVE_DARK} !important; }}
    </style>
    """,
    unsafe_allow_html=True,
)

def bubble_pack_html(active_names: list[str], height: int = PACK_HEIGHT) -> str:
    """Render `active_names` as circles packed into a FIXED area via D3's circle-packing
    layout (d3.pack): every test gets equal weight, so as the candidate list shrinks, each
    surviving circle automatically grows to fill more of the same space — down to one
    circle filling almost the whole area once a single test remains. No manual size math;
    d3.pack works out an efficient packing for whatever count it's given.

    Each label is wrapped onto as many lines as it needs and shrunk until every line fits
    inside a square inscribed in that circle (guaranteeing the whole block stays inside the
    circle, not just close to it) — measured with the browser's real text metrics
    (getComputedTextLength), so the full test name always shows, never truncated, at
    whatever size the circle currently allows.

    Note: components.html draws this in a fresh iframe every Streamlit rerun, so circles
    animate in (radius growing from 0) each time the set changes, but don't smoothly morph
    from their previous position/size across reruns — that would need a persistent custom
    component instead of this simple embed.
    """
    data = [{"name": n, "value": 1} for n in active_names]
    return f"""
<div id="bubble-wrap"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<script>
(function () {{
    const data = {json.dumps(data)};
    const width = {PACK_WIDTH};
    const height = {height};

    const root = d3.pack()
        .size([width, height])
        .padding(10)
        (d3.hierarchy({{ children: data }}).sum(d => d.value));

    const svg = d3.select('#bubble-wrap')
        .append('svg')
        .attr('viewBox', `0 0 ${{width}} ${{height}}`)
        .attr('width', '100%')
        .attr('height', height)
        .style('display', 'block');

    const nodes = svg.selectAll('g.bubble')
        .data(root.leaves())
        .join('g')
        .attr('class', 'bubble')
        .attr('transform', d => `translate(${{d.x}},${{d.y}})`);

    // Every bubble gets its own muted green -- deterministic per test name (so a given test
    // is always the same shade across reruns, not flickering to a new random color each
    // time), drawn from a wide green band (olive, moss, sage, forest, pine, sea green) but
    // capped away from yellow-green/lime and away from bright, saturated hues.
    function hashString(str) {{
        let h = 0;
        for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) | 0;
        return Math.abs(h);
    }}
    function mutedGreenFor(name) {{
        const h = hashString(name);
        const hue = 75 + (h % 80);              // 75-155: olive through moss/forest to sea green
        const sat = 22 + ((h >> 5) % 20);        // 22-41%: muted, never neon
        const light = 26 + ((h >> 9) % 20);      // 26-45%: dark-to-mid, never pale or lime-bright
        return d3.hsl(hue, sat / 100, light / 100);
    }}

    nodes.append('title').text(d => d.data.name);

    nodes.append('circle')
        .attr('r', 0)
        .attr('fill', d => mutedGreenFor(d.data.name).toString())
        .transition().duration(650).ease(d3.easeCubicOut)
        .attr('r', d => d.r);

    // A hidden text node used purely to measure real rendered width at trial font sizes —
    // getComputedTextLength() only works on an actual element in the DOM, so this is more
    // reliable than any fixed "average character width" guess, especially across mixed
    // widths like "MANCOVA" vs "Non-Parametric Multi-Way Factorial Analysis".
    const measurer = svg.append('text').attr('visibility', 'hidden');

    function widthAt(str, fontSize) {{
        measurer.style('font-size', fontSize + 'px').text(str);
        return measurer.node().getComputedTextLength();
    }}

    function wrapToFit(name, r) {{
        // Constrain to a square inscribed in the circle -- any block of text that fits
        // inside this square is guaranteed to stay inside the circle itself, with a small
        // safety margin so glyphs never touch the circle's edge.
        const box = r * Math.SQRT2 * 0.88;
        const words = name.split(/\\s+/);
        let fontSize = Math.max(r * 0.6, 4);
        let lines = [];

        while (fontSize > 3.5) {{
            lines = [];
            let current = '';
            for (const word of words) {{
                const trial = current ? current + ' ' + word : word;
                if (!current || widthAt(trial, fontSize) <= box) {{
                    current = trial;
                }} else {{
                    lines.push(current);
                    current = word;
                }}
            }}
            if (current) lines.push(current);

            const widestLine = Math.max(...lines.map(l => widthAt(l, fontSize)));
            const blockHeight = lines.length * fontSize * 1.15;

            if (widestLine <= box && blockHeight <= box) break;
            fontSize *= 0.92;
        }}
        return {{ fontSize, lines }};
    }}

    nodes.each(function (d) {{
        const {{ fontSize, lines }} = wrapToFit(d.data.name, d.r);
        const lineHeight = fontSize * 1.15;
        const startY = -((lines.length - 1) / 2) * lineHeight;

        const text = d3.select(this).append('text')
            .attr('text-anchor', 'middle')
            .attr('fill', '{WHITE}')
            .style('font-weight', 600)
            .style('font-size', '0px')
            .style('pointer-events', 'none');

        lines.forEach((line, i) => {{
            text.append('tspan')
                .attr('x', 0)
                .attr('y', startY + i * lineHeight)
                .attr('dy', '0.32em')
                .text(line);
        }});

        text.transition().duration(650).ease(d3.easeCubicOut)
            .style('font-size', fontSize + 'px');
    }});

    measurer.remove();
}})();
</script>
"""


UNSELECTED = "— Select —"


def reset_application_state():
    st.session_state.answers = {}          # {attribute_key: value}, engine vocabulary only
    st.session_state.widget_sync = {}      # {attribute_key: value last pushed into its widget}
    st.session_state.chat_transcript = []
    st.session_state.run_counter = st.session_state.get("run_counter", 0) + 1


if "answers" not in st.session_state:
    st.session_state.run_counter = 0
    reset_application_state()

st.title("StatTest Matcher")
st.caption("Adjust settings on the left panel or use the chat tool below to narrow down your study parameters.")

col_left, col_right = st.columns([1, 3])

# ========================================================
# 2. LEFT PANEL — dynamic form, driven entirely by stat_engine
# ========================================================
# Walk the SAME question order the engine itself would ask in. Each iteration:
#   - asks the engine what the next relevant question is, given answers gathered so far
#   - shows a dropdown for it, forcing it to match the underlying answer ONLY when that
#     answer changed from something other than this exact widget (i.e. the chatbot) — this
#     is what lets chat autopopulate the form without ever overriding a click the user just
#     made, since Streamlit otherwise ignores `index` once a widget's key has rendered once
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

        widget_key = f"{key}_key_{st.session_state.run_counter}"
        source_value = st.session_state.answers.get(key)

        if st.session_state.widget_sync.get(key) != source_value:
            # Something other than this widget (the chatbot, or an earlier answer changing
            # and invalidating this one) changed the underlying answer since we last synced
            # it — force the widget to catch up.
            desired_label = label_by_value.get(source_value, UNSELECTED)
            st.session_state[widget_key] = desired_label if desired_label in labels else UNSELECTED
            st.session_state.widget_sync[key] = source_value
        elif st.session_state.get(widget_key) not in labels:
            # Leftover value from a previous run_counter epoch, or one an IMPOSSIBLE rule
            # just ruled out — reset rather than let Streamlit error on an unknown option.
            st.session_state[widget_key] = UNSELECTED

        chosen_label = st.selectbox(
            attr.question,
            labels,
            help=attr.hint or None,
            key=widget_key,
        )
        chosen_value = value_by_label[chosen_label]

        if chosen_value is None:
            st.session_state.answers.pop(key, None)
            st.session_state.widget_sync.pop(key, None)
            break                                            # don't reveal later questions yet

        path_state[key] = chosen_value
        st.session_state.answers[key] = chosen_value
        st.session_state.widget_sync[key] = chosen_value

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
    active_names = [t.name for t in se.TESTS if t.name in {c.name for c in se.candidates(path_state)}]

    components.html(bubble_pack_html(active_names), height=PACK_HEIGHT + 20, scrolling=False)

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
            # Kept as the full raw merge (not snapped to the canonical subset below) so a
            # fact the user mentions ahead of its turn isn't thrown away — it'll be picked
            # up by the form/chat loop once its question actually comes up.
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