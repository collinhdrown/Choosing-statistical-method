import sys
from agent_engine import extract_variables_from_text, generate_conversational_response
from decision_router import evaluate_decision_tree

def run_consultation():
    """
    Launches a fully functioning, terminal-based AI statistical advisor
    powered by Sage logic parameters.
    """
    print("====================================================")
    print("🎓 SAGE STATS ADVISOR: INITIALIZED")
    print("Describe your research project, variables, or data setup below.")
    print("Type 'exit' to quit at any point.")
    print("====================================================\n")
    
    # Initialize the running state machine data vector
    current_state = {
        "analysis_purpose": None,
        "group_count": None,
        "data_pairing": None,
        "measurement_level": None,
        "is_normal_distribution": None
    }
    
    # Track the running conversation transcript so the AI maintains context
    transcript = ""
    
    while True:
        user_input = input("You: ")
        if user_input.strip().lower() == "exit":
            print("\nGoodbye! Good luck with your analysis.")
            break
            
        # Append latest entry to running transcription history
        transcript += f"\nUser: {user_input}"
        
        print("\n[Processing text & tracking statistical variables...]")
        
        # Step 1: Force LLM to run Structured Variable extraction
        try:
            current_state = extract_variables_from_text(transcript, current_state)
        except Exception as e:
            print(f"⚠️ Configuration Error: Make sure your OPENAI_API_KEY is active. Details: {e}")
            break
            
        print(f"📊 Running State Ledger: {current_state}")
        
        # Step 2: Push variables down the deterministic Python logical tree
        evaluation = evaluate_decision_tree(current_state)
        
        # Step 3: Branch based on whether the logical route is complete or blocked
        if evaluation["status"] == "complete":
            print("\n====================================================")
            print(f"🎯 RECOMMENDED STATISTICAL METHOD: {evaluation['test']}")
            print("====================================================\n")
            print("You have reached a valid endpoint! If you have a brand new project, change variables or restart.")
            break
        else:
            # The tree is blocked. Determine the exact field required next.
            missing_field = evaluation["ask_for"]
            
            # Have the conversational engine ask a targeted, contextual question
            ai_question = generate_conversational_response(missing_field, current_state)
            print(f"\nAdvisor: {ai_question}\n")
            
            # Keep the AI's question tracked in the transcript matrix
            transcript += f"\nAdvisor: {ai_question}"

if __name__ == "__main__":
    run_consultation()
