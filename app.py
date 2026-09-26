import os
import streamlit as st

# Pull master definitions directly from single sources of truth
from statistical_catalog import MASTER_TESTS
from main import (
    evaluate_decision_tree,
    extract_variables_from_text,
    generate_conversational_response
)

# 1. THEME INTERFACE LAYOUT CONFIGURATION
st.set_page_config(page_title="StatTest Matcher", layout="wide")

# Inject absolute deep midnight dark mode aesthetic properties
st.markdown("""
<style>
    .stApp {
        background-color: #0A1128;
        color: #E2E8F0;
    }
    h1, h2, h3, h4, p, label, .stMarkdown {
        color: #E2E8F0 !important;
    }
    div[data-baseweb="select"] > div, div[role="radiogroup"] label {
        background-color: #111E46 !important;
        color: #E2E8F0 !important;
        border-color: #1E293B !important;
    }
    div[data-testid="stHeader"] {
        background-color: rgba(10, 17, 40, 0);
    }
    .stat-bubble {
        padding: 15px;
        border-radius: 12px;
        text-align: center;
        margin: 8px;
        font-weight: bold;
        transition: all 0.3s ease;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.3);
    }
    .active-bubble {
        background-color: #1E3A8A;
        border: 2px solid #3B82F6;
        color: #F8FAFC;
    }
    .eliminated-bubble {
        background-color: #0F172A;
        border: 2px dashed #334155;
        color: #64748B;
        opacity: 0.35;
    }
    button[kind="secondary"] {
        background-color: #1E293B !important;
        color: #E2E8F0 !important;
        border: 1px solid #475569 !important;
    }
</style>
""", unsafe_allow_html=True)

# ========================================================
# 2. RUNTIME MEMORY PERSISTENCE REGISTRY
# ========================================================
def reset_application_state():
    # Evict individual widget browser locks cleanly
    keys_to_clear = ["purpose_key", "iv_key", "dv_key", "pairing_key", "norm_key"]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
            
    st.session_state.chat_transcript = []
    st.session_state.main_internal_state = {
        "analysis_purpose": None,
        "independent_variables": [],
        "dependent_variables": [],
        "data_pairing": None,
        "is_normal_distribution": None
    }

if "main_internal_state" not in st.session_state:
    reset_application_state()

# ========================================================
# 3. INTERACTIVE LAYOUT SYSTEM CODES
# ========================================================
st.title("StatTest Matcher")
st.write("Adjust settings on the left panel or utilize the chat tool down below to narrow down your study parameters.")

col_left, col_right = st.columns(2)

with col_left:
    # Resolve active baseline coordinates safely out of the internal logic ledger
    current_purpose = str(st.session_state.main_internal_state.get("analysis_purpose") or "").capitalize()
    if current_purpose not in ["Differences", "Association"]: current_purpose = "Unselected"
    
    analysis_options = ["Unselected", "Differences", "Association"]
    selected_purpose = st.selectbox(
        "Core Research Purpose:", 
        analysis_options, 
        index=analysis_options.index(current_purpose),
        key="purpose_key"
    )
    st.session_state.main_internal_state["analysis_purpose"] = None if selected_purpose == "Unselected" else selected_purpose.lower()
    
    if selected_purpose != "Unselected":
        current_iv = "More than 1" if len(st.session_state.main_internal_state.get("independent_variables", [])) > 1 else "1"
        selected_iv = st.radio("Independent Variable Count:", ["1", "More than 1"], index=["1", "More than 1"].index(current_iv), key="iv_key")
        st.session_state.main_internal_state["independent_variables"] = [{"name": "IV", "scale_type": "nominal"}] * (2 if selected_iv == "More than 1" else 1)
        
        current_dv = "More than 1" if len(st.session_state.main_internal_state.get("dependent_variables", [])) > 1 else "1"
        selected_dv = st.radio("Dependent Variable Count:", ["1", "More than 1"], index=["1", "More than 1"].index(current_dv), key="dv_key")
        st.session_state.main_internal_state["dependent_variables"] = [{"name": "DV", "scale_type": "interval_ratio"}] * (2 if selected_dv == "More than 1" else 1)
        
        if selected_purpose == "Differences":
            current_pair = str(st.session_state.main_internal_state.get("data_pairing") or "").capitalize()
            if current_pair not in ["Paired", "Unpaired"]: current_pair = "Unselected"
            
            pair_options = ["Unselected", "Paired", "Unpaired"]
            selected_pair = st.selectbox("Operational Data Pairing status:", pair_options, index=pair_options.index(current_pair), key="pairing_key")
            st.session_state.main_internal_state["data_pairing"] = None if selected_pair == "Unselected" else selected_pair.lower()
        else:
            st.session_state.main_internal_state["data_pairing"] = "any"

        current_norm = st.session_state.main_internal_state.get("is_normal_distribution")
        norm_string = "Unselected"
        if current_norm is True: norm_string = "Yes (Parametric)"
        elif current_norm is False: norm_string = "No (Non-Parametric)"
        
        norm_options = ["Unselected", "Yes (Parametric)", "No (Non-Parametric)"]
        selected_norm = st.selectbox("Normal Sample Distribution validation:", norm_options, index=norm_options.index(norm_string), key="norm_key")
        
        if selected_norm == "Unselected": st.session_state.main_internal_state["is_normal_distribution"] = None
        else: st.session_state.main_internal_state["is_normal_distribution"] = True if "Yes" in selected_norm else False

    st.markdown(" ")
    st.button("Reset Workspace", use_container_width=True, on_click=reset_application_state)

with col_right:
    # PASS CLEAN STORAGE DIRECTLY INTO MAIN.PY LOGIC WITHOUT MUTATION RE-RUNS
    evaluation = evaluate_decision_tree(st.session_state.main_internal_state)
    
    active_tests = []
    eliminated_tests = []
    
    # Calculate filtering parameters matching form layouts
    for test in MASTER_TESTS:
        is_match = True
        if st.session_state.main_internal_state["analysis_purpose"]:
            # Setup string checks matching catalog arrays
            f_purpose = st.session_state.main_internal_state["analysis_purpose"].capitalize()
            f_iv = "More than 1" if len(st.session_state.main_internal_state["independent_variables"]) > 1 else "1"
            f_dv = "More than 1" if len(st.session_state.main_internal_state["dependent_variables"]) > 1 else "1"
            
            if test["purpose"] != f_purpose: is_match = False
            if test["iv_count"] != f_iv: is_match = False
            if test["dv_count"] != f_dv: is_match = False
            
            if f_purpose == "Differences" and st.session_state.main_internal_state["data_pairing"]:
                f_pair = st.session_state.main_internal_state["data_pairing"].capitalize()
                if test["pairing"] != "Any" and test["pairing"] != f_pair: is_match = False
                
            if st.session_state.main_internal_state["is_normal_distribution"] is not None:
                f_norm = "Yes (Parametric)" if st.session_state.main_internal_state["is_normal_distribution"] else "No (Non-Parametric)"
                if test["normality"] != "Any" and test["normality"] != f_norm: is_match = False
                
        if is_match: active_tests.append(test)
        else: eliminated_tests.append(test)
            
    grid_cols = st.columns(3)
    for idx, test in enumerate(active_tests + eliminated_tests):
        current_col = grid_cols[idx % 3]
        if test in active_tests:
            current_col.markdown(f'<div class="stat-bubble active-bubble">{test["name"]}</div>', unsafe_allow_html=True)
        else:
            current_col.markdown(f'<div class="stat-bubble eliminated-bubble">{test["name"]}</div>', unsafe_allow_html=True)
            
    if evaluation["status"] == "complete":
        st.success(f"Optimal Recommendation: **{evaluation['test']}**")
        
    st.markdown("---")
    
    for msg in st.session_state.chat_transcript:
        if msg["role"] == "user": st.markdown(f"**You:** {msg['content']}")
        else: st.markdown(f"**Advisor:** {msg['content']}")
            
    user_query = st.chat_input("Describe your research questions, variables setups, or data shapes...")
    if user_query:
        st.session_state.chat_transcript.append({"role": "user", "content": user_query})
        
        with st.spinner("Analyzing variables context..."):
            history_text = "".join([f"\n{m['role']}: {m['content']}" for m in st.session_state.chat_transcript])
            
            # EXTRACT VARIABLES CONTEXT SAFELY FROM THE TRANSCRIPT
            st.session_state.main_internal_state = extract_variables_from_text(history_text, st.session_state.main_internal_state)
            
            # RE-EVALUATE AND GENERATE NATIVE ADVISOR RESPONSER PAYLOAD
            post_eval = evaluate_decision_tree(st.session_state.main_internal_state)
            ai_reply = generate_conversational_response(post_eval["ask_for"], st.session_state.main_internal_state)
            st.session_state.chat_transcript.append({"role": "assistant", "content": ai_reply})
            
        st.rerun()
