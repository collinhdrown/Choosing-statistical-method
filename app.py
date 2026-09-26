import os
import sys
import streamlit as st
from openai import OpenAI
from pydantic import BaseModel
from typing import Optional, List
from dotenv import load_dotenv

# ========================================================
# 1. INITIALIZATION & VAULT SETUPS
# ========================================================
script_directory = os.path.dirname(os.path.abspath(__file__))
env_file_path = os.path.join(script_directory, ".env")
load_dotenv(dotenv_path=env_file_path)

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("⚠️ Key Configuration Error: Could not read OPENAI_API_KEY from your .env file.")
    st.stop()

client = OpenAI(api_key=api_key)

st.set_page_config(page_title="Sage Stats Interactive Dashboard", layout="wide", page_icon=":herb:")

st.markdown("""
<style>
    .stat-bubble {
        padding: 15px;
        border-radius: 12px;
        text-align: center;
        margin: 8px;
        font-weight: bold;
        transition: all 0.3s ease;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .active-bubble {
        background-color: #E3F2FD;
        border: 2px solid #1E88E5;
        color: #0D47A1;
    }
    .eliminated-bubble {
        background-color: #F5F5F5;
        border: 2px dashed #E0E0E0;
        color: #9E9E9E;
        opacity: 0.35;
    }
</style>
""", unsafe_allow_html=True)

# ========================================================
# 2. BULLETPROOF STATE INITIALIZATION & RESET MANAGER
# ========================================================
# This callback manager runs BEFORE the page compiles to forcefully smash the cache
def reset_application_state():
    # Forcefully clear the hidden widget key memory storage
    keys_to_clear = ["purpose_key", "iv_key", "dv_key", "pairing_key", "norm_key"]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
            
    # Reset underlying state models back to clean defaults
    st.session_state.analysis_purpose = "Unselected"
    st.session_state.iv_count = "1"
    st.session_state.dv_count = "1"
    st.session_state.data_pairing = "Unselected"
    st.session_state.is_normal_distribution = "Unselected"
    st.session_state.chat_transcript = []

# Safe initialization checkpoint
if "analysis_purpose" not in st.session_state:
    reset_application_state()

# ========================================================
# 3. STATISTICAL MASTER DICTIONARY
# ========================================================
MASTER_TESTS = [
    {"name": "Independent Samples t-test", "purpose": "Differences", "iv_count": "1", "dv_count": "1", "pairing": "Unpaired", "normality": "Yes (Parametric)"},
    {"name": "Mann-Whitney U Test", "purpose": "Differences", "iv_count": "1", "dv_count": "1", "pairing": "Unpaired", "normality": "No (Non-Parametric)"},
    {"name": "Paired Samples t-test", "purpose": "Differences", "iv_count": "1", "dv_count": "1", "pairing": "Paired", "normality": "Yes (Parametric)"},
    {"name": "Wilcoxon Signed-Rank Test", "purpose": "Differences", "iv_count": "1", "dv_count": "1", "pairing": "Paired", "normality": "No (Non-Parametric)"},
    {"name": "One-Way ANOVA", "purpose": "Differences", "iv_count": "1", "dv_count": "1", "pairing": "Unpaired", "normality": "Yes (Parametric)"},
    {"name": "Kruskal-Wallis H Test", "purpose": "Differences", "iv_count": "1", "dv_count": "1", "pairing": "Unpaired", "normality": "No (Non-Parametric)"},
    {"name": "Pearson's r Correlation", "purpose": "Association", "iv_count": "1", "dv_count": "1", "pairing": "Any", "normality": "Yes (Parametric)"},
    {"name": "Spearman's Rank Correlation", "purpose": "Association", "iv_count": "1", "dv_count": "1", "pairing": "Any", "normality": "No (Non-Parametric)"},
    {"name": "Chi-Square Test of Independence", "purpose": "Association", "iv_count": "1", "dv_count": "1", "pairing": "Any", "normality": "Any"},
    {"name": "Multiple Linear Regression", "purpose": "Association", "iv_count": "More than 1", "dv_count": "1", "pairing": "Any", "normality": "Yes (Parametric)"},
    {"name": "One-Way MANOVA", "purpose": "Differences", "iv_count": "1", "dv_count": "More than 1", "pairing": "Unpaired", "normality": "Yes (Parametric)"},
    {"name": "Hierarchical Linear Modeling (HLM)", "purpose": "Association", "iv_count": "More than 1", "dv_count": "1", "pairing": "Any", "normality": "Any"}
]

class VariableModel(BaseModel):
    name: str
    scale_type: str

class ExtractedResearchState(BaseModel):
    analysis_purpose: Optional[str] = None         
    independent_variables: list[VariableModel] = []
    dependent_variables: list[VariableModel] = []
    data_pairing: Optional[str] = None             
    is_normal_distribution: Optional[bool] = None

def parse_chat_intent_into_state(user_message: str):
    history_transcript = "".join([f"\n{m['role']}: {m['content']}" for m in st.session_state.chat_transcript]) + f"\nuser: {user_message}"
    prompt = (
        "Extract variables. purpose='differences' if comparing group means. purpose='association' if running correlations/regressions. "
        "GPA/height/weight are ALWAYS 'interval_ratio'. SES is ordinal or interval_ratio. Never leave scale_type empty."
    )
    response = client.beta.chat.completions.parse(
        model="gpt-4o", messages=[{"role": "system", "content": prompt}, {"role": "user", "content": history_transcript}], response_format=ExtractedResearchState
    )
    data = response.choices[0].message.parsed
    if data.analysis_purpose:
        st.session_state.analysis_purpose = data.analysis_purpose.capitalize()
    if len(data.independent_variables) > 1:
        st.session_state.iv_count = "More than 1"
    elif len(data.independent_variables) == 1:
        st.session_state.iv_count = "1"
    if data.data_pairing:
        st.session_state.data_pairing = data.data_pairing.capitalize()
    if data.is_normal_distribution is not None:
        st.session_state.is_normal_distribution = "Yes (Parametric)" if data.is_normal_distribution else "No (Non-Parametric)"
# ========================================================
# 4. FORM AND LAYOUT ENGINE RENDERING
# ========================================================
st.title("Which Statistical Test Should I Use?")

col_left, col_right = st.columns(2)

with col_left:
    st.markdown("### Design Details")
    
    analysis_options = ["Unselected", "Differences", "Association"]
    st.session_state.analysis_purpose = st.selectbox(
        "1. Core Research Purpose:", 
        analysis_options, 
        index=analysis_options.index(st.session_state.analysis_purpose) if st.session_state.analysis_purpose in analysis_options else 0,
        key="purpose_key"
    )
    
    if st.session_state.analysis_purpose != "Unselected":
        iv_options = ["1", "More than 1"]
        st.session_state.iv_count = st.radio(
            "2. Independent Variable Count:", 
            iv_options, 
            index=iv_options.index(st.session_state.iv_count) if st.session_state.iv_count in iv_options else 0,
            key="iv_key"
        )
        
        dv_options = ["1", "More than 1"]
        st.session_state.dv_count = st.radio(
            "3. Dependent Variable Count:", 
            dv_options, 
            index=dv_options.index(st.session_state.dv_count) if st.session_state.dv_count in dv_options else 0,
            key="dv_key"
        )
        
        if st.session_state.analysis_purpose == "Differences":
            pair_options = ["Unselected", "Paired", "Unpaired"]
            st.session_state.data_pairing = st.selectbox(
                "4. Operational Data Pairing status:", 
                pair_options, 
                index=pair_options.index(st.session_state.data_pairing) if st.session_state.data_pairing in pair_options else 0,
                key="pairing_key"
            )
        else:
            st.session_state.data_pairing = "Any"

        norm_options = ["Unselected", "Yes (Parametric)", "No (Non-Parametric)"]
        st.session_state.is_normal_distribution = st.selectbox(
            "5. Normal Sample Distribution validation:", 
            norm_options, 
            index=norm_options.index(st.session_state.is_normal_distribution) if st.session_state.is_normal_distribution in norm_options else 0,
            key="norm_key"
        )

    st.markdown(" ")
    st.button("Reset Workspace", use_container_width=True, on_click=reset_application_state)

with col_right:
    st.markdown("### ")
    
    active_tests = []
    eliminated_tests = []
    
    for test in MASTER_TESTS:
        is_match = True
        
        if st.session_state.analysis_purpose != "Unselected":
            if test["purpose"] != st.session_state.analysis_purpose: is_match = False
            if test["iv_count"] != st.session_state.iv_count: is_match = False
            if test["dv_count"] != st.session_state.dv_count: is_match = False
            if st.session_state.analysis_purpose == "Differences" and st.session_state.data_pairing != "Unselected" and test["pairing"] != "Any" and test["pairing"] != st.session_state.data_pairing:
                is_match = False
            if st.session_state.is_normal_distribution != "Unselected" and test["normality"] != "Any" and test["normality"] != st.session_state.is_normal_distribution:
                is_match = False
            
        if is_match:
            active_tests.append(test)
        else:
            eliminated_tests.append(test)
            
    all_render_list = active_tests + eliminated_tests
    grid_cols = st.columns(3)
    
    for idx, test in enumerate(all_render_list):
        current_col = grid_cols[idx % 3]
        if test in active_tests:
            current_col.markdown(f'<div class="stat-bubble active-bubble">🔵 {test["name"]}</div>', unsafe_allow_html=True)
        else:
            current_col.markdown(f'<div class="stat-bubble eliminated-bubble">⚪ {test["name"]}</div>', unsafe_allow_html=True)
            
    if len(active_tests) == 1:
        st.success(f"###  Recommended: **{active_tests[0]['name']}**")
        
    st.markdown("---")
    st.markdown("### Describe your research design, and I'll help narrow down your options")
    
    for msg in st.session_state.chat_transcript:
        if msg["role"] == "user":
            st.markdown(f"** You:** {msg['content']}")
        else:
            st.markdown(f"* Advisor:** {msg['content']}")
            
    user_query = st.chat_input("Describe your research questions, variables array setups, or data shapes...")
    if user_query:
        st.session_state.chat_transcript.append({"role": "user", "content": user_query})
        with st.spinner("Sage AI engine analyzing variables context..."):
            parse_chat_intent_into_state(user_query)
            prompt_followup = f"Friendly 1-sentence conversational follow-up asking for the next missing trait. Context: purpose={st.session_state.analysis_purpose}, pairing={st.session_state.data_pairing}, normal={st.session_state.is_normal_distribution}."
            ai_reply = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt_followup}]).choices[0].message.content.strip()
            st.session_state.chat_transcript.append({"role": "assistant", "content": ai_reply})
        st.rerun()
