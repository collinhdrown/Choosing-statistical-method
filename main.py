import os, sys
from openai import OpenAI
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("⚠️ Key Configuration Error: Your .env file cannot be read.")
    sys.exit(1)
client = OpenAI(api_key=api_key)
#2 Identify Variables
class VariableModel(BaseModel):
    name: str
    scale_type: str  # Must be: "nominal", "ordinal", or "interval_ratio"

class ExtractedResearchState(BaseModel):
    analysis_purpose: Optional[str] = None      
    independent_variables: list[VariableModel] = [] 
    dependent_variables: list[VariableModel] = []   
    data_pairing: Optional[str] = None          
    is_normal_distribution: Optional[bool] = None
#3 Evaluate Decision Tree
def evaluate_decision_tree(state: dict):
    purpose = state.get("analysis_purpose")
    if not purpose: return {"status": "incomplete", "ask_for": "analysis_purpose"}

    ivs = state.get("independent_variables", [])
    dvs = state.get("dependent_variables", [])
    if not ivs: return {"status": "incomplete", "ask_for": "independent_variables"}
    if not dvs: return {"status": "incomplete", "ask_for": "dependent_variables"}

    iv_count = len(ivs)
    dv_count = len(dvs)
    p_str = str(purpose).lower()
    is_diff = "diff" in p_str or "compare" in p_str or "mean" in p_str or "average" in p_str or "test" in p_str
    is_assoc = "assoc" in p_str or "relat" in p_str or "corr" in p_str or "predict" in p_str

    if is_diff:
        pairing = state.get("data_pairing")
        if not pairing: return {"status": "incomplete", "ask_for": "data_pairing"}
        
        # MULTIPLE DEPENDENT VARIABLES (MANOVA Gateway)
        if dv_count > 1:
            if all(d["scale_type"] == "interval_ratio" for d in dvs):
                return {"status": "complete", "test": f"One-Way MANOVA (tracking outcomes: {[d['name'] for d in dvs]})"}
            return {"status": "complete", "test": "Advanced Multivariate General Linear Model"}

        # MULTIPLE INDEPENDENT VARIABLES (Factorial / Two-Way ANOVA Gateway)
        if iv_count > 1:
            if dvs[0]["scale_type"] == "interval_ratio" and all(i["scale_type"] == "nominal" for i in ivs):
                norm = state.get("is_normal_distribution")
                if norm is None: return {"status": "incomplete", "ask_for": "is_normal_distribution"}
                return {"status": "complete", "test": f"{iv_count}-Way Factorial ANOVA" if norm else "Scheirer-Ray-Hare Test"}

        # STANDARD SINGLE VARIABLES (1 IV, 1 DV)
        iv_type, dv_type = ivs[0]["scale_type"], dvs[0]["scale_type"]
        if iv_type == "nominal":
            if pairing == "unpaired":
                if dv_type == "nominal": return {"status": "complete", "test": "Chi-Square Test of Independence"}
                if dv_type == "ordinal": return {"status": "complete", "test": "Mann-Whitney U Test"}
                if dv_type == "interval_ratio":
                    norm = state.get("is_normal_distribution")
                    if norm is None: return {"status": "incomplete", "ask_for": "is_normal_distribution"}
                    return {"status": "complete", "test": "Independent Samples t-test" if norm else "Mann-Whitney U Test"}
            if pairing == "paired":
                if dv_type == "nominal": return {"status": "complete", "test": "McNemar's Test"}
                if dv_type == "ordinal": return {"status": "complete", "test": "Wilcoxon Signed-Rank Test"}
                if dv_type == "interval_ratio":
                    norm = state.get("is_normal_distribution")
                    if norm is None: return {"status": "incomplete", "ask_for": "is_normal_distribution"}
                    return {"status": "complete", "test": "Paired Samples t-test" if norm else "Wilcoxon Signed-Rank Test"}

    if is_assoc:
        # REGRESSION GATEWAY (Multiple Predictor Variables)
        if iv_count > 1:
            if not dvs[0].get("scale_type"): return {"status": "incomplete", "ask_for": "measurement_level"}
            if dvs[0]["scale_type"] == "interval_ratio": return {"status": "complete", "test": "Multiple Linear Regression"}
            if dvs[0]["scale_type"] == "nominal": return {"status": "complete", "test": "Multiple Logistic Regression"}
        
        # STANDARD CORRELATIONS & ASSOCIATIONS (1 IV, 1 DV)
        # Extract variables from list models safely
        iv_model = ivs[0]
        dv_model = dvs[0]
        
        iv_type = str(iv_model.get("scale_type") or "").lower()
        dv_type = str(dv_model.get("scale_type") or "").lower()
        
        # CRITICAL PROTECTION GATES: If scales are blank, force a prompt to discover them
        if not iv_type or not dv_type:
            return {"status": "incomplete", "ask_for": "measurement_level"}

        # Case 1: Both variables are continuous numbers
        if iv_type == "interval_ratio" and dv_type == "interval_ratio":
            norm = state.get("is_normal_distribution")
            if norm is None: return {"status": "incomplete", "ask_for": "is_normal_distribution"}
            return {"status": "complete", "test": "Pearson's r Correlation" if norm else "Spearman's Rank Correlation"}
        
        # Case 2: One variable is a Category (Nominal) and one is Continuous (Interval/Ratio)
        if (iv_type == "nominal" and dv_type == "interval_ratio") or (iv_type == "interval_ratio" and dv_type == "nominal"):
            group_count = state.get("group_count_meta")
            iv_name = iv_model.get("name", "Predictor")
            dv_name = dv_model.get("name", "Outcome")
            if group_count == "two":
                return {"status": "complete", "test": f"Point-Biserial Correlation (Relationship between '{iv_name}' and '{dv_name}')"}
            else:
                return {"status": "complete", "test": f"Generalized Linear Model / Multinomial Regression (Modeling impact of '{iv_name}' on '{dv_name}')"}
            
        # Case 3: Both variables are Category labels (Nominal)
        if iv_type == "nominal" and dv_type == "nominal": 
            return {"status": "complete", "test": "Chi-Square Test of Independence (with Cramer's V)"}
            
        # Case 4: Any fallback ranking scale data (Ordinal)
        return {"status": "complete", "test": "Spearman's Rank Correlation (rho)"}

    return {"status": "incomplete", "ask_for": "clarification"}


# Section 4
def extract_variables_from_text(conversation_history: str, current_known_state: dict) -> dict:
    prompt = (
        "You are a strict statistical data gatekeeper. Analyze the transcript. "
        "CRITICAL RULES: "
        "1. Do NOT hallucinate, invent, or guess variables. Only extract exactly what the user types. "
        "2. If the user uses ambiguous language like 'analyze', 'look at', 'study', or 'explore' "
        "WITHOUT explicitly stating if they want to 'compare differences between groups' OR 'find a correlation/relationship', "
        "you MUST leave analysis_purpose as null. Do not guess. "
        "3. Only set purpose='differences' if they say compare/difference. Only set purpose='association' if they say correlate/predict/relate. "
        "4. Extract real factors into independent_variables or dependent_variables arrays with scale_type "
        "('nominal', 'ordinal', or 'interval_ratio'). If ambiguous, leave scale_type null so the system can prompt. "
        f"Baseline: {current_known_state}"
    )
    response = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[{"role": "system", "content": prompt}, {"role": "user", "content": f"Transcript:\n{conversation_history}"}],
        response_format=ExtractedResearchState,
    )
    extracted_data = response.choices[0].message.parsed.model_dump()
    updated_state = current_known_state.copy()
    for key, value in extracted_data.items():
        if value: updated_state[key] = value
    return updated_state
# Section 5
def generate_conversational_response(missing_variable: str, current_state: dict) -> str:
    configs = {
        "analysis_purpose": {"q": "What is the primary goal of your analysis?", "e": "For example, are you trying to see if there is a difference between groups, or looking for an association?"},
        "group_count": {"q": "Can you let me know how many groups or conditions you are comparing?", "e": "For example, are you comparing exactly two groups or more than two groups?"},
        "data_pairing": {"q": "Can you let me know if your data is paired or unpaired?", "e": "For example, are you testing the same individuals twice (paired), or comparing completely separate, independent groups (unpaired)?"},
        "measurement_level": {"q": "Can you let me know how your outcome variable is measured?", "e": "For example, categorical categories (nominal), ranked/ordered scales (ordinal), or continuous numeric measurements (interval_ratio)?"},
        "is_normal_distribution": {"q": "Can you let me know if your data is normally distributed?", "e": "For example, you can check this by running a formal normality test or by visually checking if the scores form a symmetrical, bell-shaped curve."}
    }
    config = configs.get(missing_variable, {"q": "Can you clarify the next detail regarding your data?", "e": "Please provide a brief description of your variables."})
    prompt = f"Ask for missing property using exact pattern. QUESTION: '{config['q']}' EXAMPLES: '{config['e']}' INSTRUCTIONS: Deliver ONLY the direct question followed immediately by the examples. Exactly 2 sentences total."
    response = client.client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}]) if hasattr(client, 'client') else client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
    return response.choices[0].message.content.strip()

print("====================================================\n🎓 SAGE STATS ADVISOR: INITIALIZED (UNIVERSAL RUNTIME)\nDescribe your research project below.\n====================================================\n")
current_state = {"analysis_purpose": None, "group_count": None, "data_pairing": None, "measurement_level": None, "is_normal_distribution": None}
transcript = ""
while True:
    user_input = input("You: ")
    if user_input.strip().lower() == "exit": break
    transcript += f"\nUser: {user_input}"
    print("\n[Analyzing data properties...]")
    current_state = extract_variables_from_text(transcript, current_state)
    print(f"📊 Running State Ledger: {current_state}")
    evaluation = evaluate_decision_tree(current_state)
    if evaluation["status"] == "complete":
        print(f"\n🎯 RECOMMENDED STATISTICAL METHOD: {evaluation['test']}\n")
        break
    else:
        ai_question = generate_conversational_response(evaluation["ask_for"], current_state)
        print(f"\nAdvisor: {ai_question}\n")
        transcript += f"\nAdvisor: {ai_question}"
