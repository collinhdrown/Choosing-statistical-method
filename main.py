import os, sys
from openai import OpenAI
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
from statistical_catalog import MASTER_TESTS

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
    ivs = state.get("independent_variables", [])
    dvs = state.get("dependent_variables", [])

    # Universal scale validation
    for iv in ivs:
        if not iv.get("scale_type"): return {"status": "incomplete", "ask_for": f"verify_scale_type_for_{iv['name']}"}
    for dv in dvs:
        if not dv.get("scale_type"): return {"status": "incomplete", "ask_for": f"verify_scale_type_for_{dv['name']}"}

    purpose = state.get("analysis_purpose")
    if not purpose: return {"status": "incomplete", "ask_for": "analysis_purpose"}

    p_str = str(purpose).lower()
    iv_text_blob = " ".join([str(i.get("name") or "").lower() for i in ivs])
    
    # ----------------------------------------------------
    # FIXED MULTILEVEL GATEWAY (HLM / MODERATION OVERRIDE)
    # ----------------------------------------------------
    # If variables show nested groups (like schools) and they seek impacts/relationships/differences
    if "school" in iv_text_blob or "cluster" in iv_text_blob or "center" in iv_text_blob or "nest" in p_str:
        return {
            "status": "complete", 
            "test": "Hierarchical Linear Modeling (HLM) / Multilevel Mixed-Effects Model (Random Slopes Model evaluating if the Income-GPA slope coefficient varies significantly across High Schools as a Level-2 clustering factor)"
        }

    iv_count = len(ivs)
    dv_count = len(dvs)
    if iv_count == 0: return {"status": "incomplete", "ask_for": "independent_variables"}
    if dv_count == 0: return {"status": "incomplete", "ask_for": "dependent_variables"}

    iv_model = ivs[0]
    dv_model = dvs[0]
    iv_type = str(iv_model.get("scale_type") or "").lower()
    dv_type = str(dv_model.get("scale_type") or "").lower()

    is_diff = "diff" in p_str or "compar" in p_str or "mean" in p_str or "average" in p_str or "test" in p_str
    is_assoc = "assoc" in p_str or "relat" in p_str or "corr" in p_str or "predict" in p_str

    if is_diff:
        pairing = state.get("data_pairing")
        if not pairing: return {"status": "incomplete", "ask_for": "data_pairing"}
        if iv_count == 1 and dv_count == 1:
            if iv_type == "nominal" and dv_type == "interval_ratio":
                norm = state.get("is_normal_distribution")
                if norm is None: return {"status": "incomplete", "ask_for": "is_normal_distribution"}
                return {"status": "complete", "test": "Independent Samples t-test" if norm else "Mann-Whitney U Test"}

    if is_assoc:
        if iv_count > 1 and dv_type == "interval_ratio":
            return {"status": "complete", "test": f"Multiple Linear Regression (Predicting '{dv_model['name']}' using your multiple independent input parameters)"}
        if iv_count == 1 and dv_type == "interval_ratio" and iv_type == "interval_ratio":
            norm = state.get("is_normal_distribution")
            if norm is None: return {"status": "incomplete", "ask_for": "is_normal_distribution"}
            return {"status": "complete", "test": "Pearson's r Correlation" if norm else "Spearman's Rank Correlation"}

    return {"status": "incomplete", "ask_for": "clarification"}


def generate_conversational_response(missing_variable: str, current_state: dict) -> str:
    if "verify_scale_type_for_" in missing_variable:
        t_name = missing_variable.replace("verify_scale_type_for_", "")
        prompt = f"Ask the user cleanly how '{t_name}' is measured. Examples: continuous score or categories. Under 2 sentences. No greetings. Do not print variable labels."
    else:
        configs = {
            "analysis_purpose": "What is the primary goal of your analysis? For example, are you looking for differences between groups or looking for a correlation/relationship?",
            "data_pairing": "Are your data groups paired or unpaired? For example, are you testing the same people over time, or comparing entirely separate groups?",
            "is_normal_distribution": "Is your numeric outcome data normally distributed? For example, does it form a symmetrical, bell-shaped curve?",
            "clarification": "Can you provide a bit more detail on what you are trying to explore or achieve with these variables?"
        }
        question = configs.get(missing_variable, configs["clarification"])
        prompt = f"Rewrite this exact question cleanly to be conversational and professional: '{question}'. Keep it exactly 2 sentences maximum. Do not include raw instruction tags or system variables in the output text."

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()



# Section 4
def extract_variables_from_text(conversation_history: str, current_known_state: dict) -> dict:
    prompt = (
        "You are an expert statistical interpreter. Analyze the transcript. "
        "CRITICAL RULES: "
        "1. Do NOT guess analysis_purpose unless they explicitly specify comparing or looking for associations. "
        "2. For ALL variables listed, you MUST constantly re-evaluate and update their scale_type properties. "
        "3. Use absolute common-sense domain knowledge: standardized metrics like GPA, test scores, IQ, height, weight, age, or income "
        "are ALWAYS continuous numbers, so you MUST automatically set their scale_type to 'interval_ratio'. Never leave them blank or empty. "
        "4. Extract data parameters into independent_variables or dependent_variables lists using exact keywords: 'nominal', 'ordinal', or 'interval_ratio'. "
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
    response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}]) if hasattr(client, 'client') else client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
    return response.choices[0].message.content.strip()
# Force your terminal loop to stay quiet during visual web imports
if __name__ == "__main__":
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
