import os
import sys
from openai import OpenAI
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

# ========================================================
# 1. INITIALIZATION & CREDENTIAL LOADING
# ========================================================
load_dotenv()

# Verify key exists to catch issues early
api_key = os.getenv("OPENAI_API_KEY")
if not api_key or "YOUR" in api_key or "your_" in api_key:
    print("⚠️ Key Configuration Error: Please open your '.env' file and replace the placeholder text with your real sk-proj-... OpenAI API key.")
    sys.exit(1)

client = OpenAI(api_key=api_key)

# ========================================================
# 2. DATA SCHEMAS & VARIABLES
# ========================================================
class ExtractedResearchState(BaseModel):
    analysis_purpose: Optional[str] = None      # "differences" vs "association"
    group_count: Optional[str] = None           # "two" vs "more_than_two"
    data_pairing: Optional[str] = None          # "paired" vs "unpaired"
    measurement_level: Optional[str] = None     # "nominal", "ordinal", "interval_ratio"
    is_normal_distribution: Optional[bool] = None

# ========================================================
# 3. DETERMINISTIC LOGICAL ROUTER (SAGE FLOWCHART)
# ========================================================
def evaluate_decision_tree(state: dict):
    purpose = state.get("analysis_purpose")
    if not purpose:
        return {"status": "incomplete", "ask_for": "analysis_purpose"}

    # --- BRANCH A: LOOKING FOR DIFFERENCES ---
    if purpose == "differences":
        groups = state.get("group_count")
        if not groups: return {"status": "incomplete", "ask_for": "group_count"}

        pairing = state.get("data_pairing")
        if not pairing: return {"status": "incomplete", "ask_for": "data_pairing"}

        level = state.get("measurement_level")
        if not level: return {"status": "incomplete", "ask_for": "measurement_level"}

        # Two Groups Paths
        if groups == "two":
            if pairing == "unpaired":
                if level == "nominal": return {"status": "complete", "test": "Chi-Square Test of Independence"}
                if level == "ordinal": return {"status": "complete", "test": "Mann-Whitney U Test"}
                if level == "interval_ratio":
                    norm = state.get("is_normal_distribution")
                    if norm is None: return {"status": "incomplete", "ask_for": "is_normal_distribution"}
                    return {"status": "complete", "test": "Independent Samples t-test" if norm else "Mann-Whitney U Test"}
            
            if pairing == "paired":
                if level == "nominal": return {"status": "complete", "test": "McNemar's Test"}
                if level == "ordinal": return {"status": "complete", "test": "Wilcoxon Signed-Rank Test"}
                if level == "interval_ratio":
                    norm = state.get("is_normal_distribution")
                    if norm is None: return {"status": "incomplete", "ask_for": "is_normal_distribution"}
                    return {"status": "complete", "test": "Paired Samples t-test" if norm else "Wilcoxon Signed-Rank Test"}

        # More Than Two Groups Paths
        if groups == "more_than_two":
            if pairing == "unpaired":
                if level == "nominal": return {"status": "complete", "test": "Chi-Square Test of Independence"}
                if level == "ordinal": return {"status": "complete", "test": "Kruskal-Wallis H Test"}
                if level == "interval_ratio":
                    norm = state.get("is_normal_distribution")
                    if norm is None: return {"status": "incomplete", "ask_for": "is_normal_distribution"}
                    return {"status": "complete", "test": "One-Way ANOVA" if norm else "Kruskal-Wallis H Test"}

    # --- BRANCH B: LOOKING FOR ASSOCIATIONS ---
    if purpose == "association":
        level = state.get("measurement_level")
        if not level: return {"status": "incomplete", "ask_for": "measurement_level"}
        
        if level == "nominal": return {"status": "complete", "test": "Chi-Square Test (with Cramer's V)"}
        if level == "ordinal": return {"status": "complete", "test": "Spearman's Rank Correlation (rho)"}
        if level == "interval_ratio":
            norm = state.get("is_normal_distribution")
            if norm is None: return {"status": "incomplete", "ask_for": "is_normal_distribution"}
            return {"status": "complete", "test": "Pearson's r Correlation" if norm else "Spearman's Rank Correlation"}

    return {"status": "incomplete", "ask_for": "clarification"}

# ========================================================
# 4. LLM EXTRACTION & REASONING ENGINES
# ========================================================
def extract_variables_from_text(conversation_history: str, current_known_state: dict) -> dict:
    system_prompt = f"""
    You are a precise data extraction engine for a statistical consultation tool. 
    Analyze the incoming user conversation history. Look for metrics that map to our statistical parameters.
    
    GUIDELINES:
    1. 'differences' if comparing groups. 'association' if looking for relationships/correlations.
    2. 'two' or 'more_than_two' if group amounts are mentioned.
    3. 'paired' if tracking the same individuals twice over time. 'unpaired' if comparing completely separate entities.
    4. 'nominal' for binary/categories, 'ordinal' for rankings/Likert, 'interval_ratio' for continuous integers.
    5. 'is_normal_distribution': True or False if they specify normality.
    
    Leave values as null if they are completely unmentioned. Do not guess.
    Current baseline: {current_known_state}
    """
    try:
        response = client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Conversation Transcript:\n{conversation_history}"}
            ],
            response_format=ExtractedResearchState,
        )
        extracted_data = response.choices[0].message.parsed.model_dump()
        updated_state = current_known_state.copy()
        for key, value in extracted_data.items():
            if value is not None:
                updated_state[key] = value
        return updated_state
    except Exception as e:
        print(f"⚠️ OpenAI Communication Error: Check your credits/billing platform connection status. Details: {e}")
        sys.exit(1)

def generate_conversational_response(missing_variable: str, current_state: dict) -> str:
    prompt = f"""
    You are a friendly statistical consultant utilizing Sage's 'Which Stats Test' routing engine.
    Current data profile vector: {current_state}
    
    We need to discover this metric: '{missing_variable}'
    
    Ask a natural follow-up question to discover this piece of data. 
    Explain *why* this choice matters simply, completely avoiding confusing academic jargon.
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices.message.content

# ========================================================
# 5. CORE EXECUTION MAIN LOOP
# ========================================================
def run_consultation():
    print("====================================================")
    print("🎓 SAGE STATS ADVISOR: INITIALIZED")
    print("Describe your research project, variables, or data setup below.")
    print("Type 'exit' to quit at any point.")
    print("====================================================\n")
    
    current_state = {
        "analysis_purpose": None,
        "group_count": None,
        "data_pairing": None,
        "measurement_level": None,
        "is_normal_distribution": None
    }
    transcript = ""
    
    while True:
        user_input = input("You: ")
        if user_input.strip().lower() == "exit":
            print("\nGoodbye!")
            break
            
        transcript += f"\nUser: {user_input}"
        print("\n[Analyzing data properties...]")
        
        current_state = extract_variables_from_text(transcript, current_state)
        print(f"📊 Running State Ledger: {current_state}")
        
        evaluation = evaluate_decision_tree(current_state)
        if evaluation["status"] == "complete":
            print("\n====================================================")
            print(f"🎯 RECOMMENDED STATISTICAL METHOD: {evaluation['test']}")
            print("====================================================\n")
            break
        else:
            missing_field = evaluation["ask_for"]
            ai_question = generate_conversational_response(missing_field, current_state)
            print(f"\nAdvisor: {ai_question}\n")
            transcript += f"\nAdvisor: {ai_question}"

if __name__ == "__main__":
    run_consultation()
