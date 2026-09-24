import os
from openai import OpenAI
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

# Load hidden environment variables from your .env file
load_dotenv()

# Initialize the secure connection to OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Define the exact data model the AI is forced to extract from the user's messy text
class ExtractedResearchState(BaseModel):
    analysis_purpose: Optional[str] = None      # Must be exactly "differences" or "association"
    group_count: Optional[str] = None           # Must be exactly "two" or "more_than_two"
    data_pairing: Optional[str] = None          # Must be exactly "paired" or "unpaired"
    measurement_level: Optional[str] = None     # Must be exactly "nominal", "ordinal", or "interval_ratio"
    is_normal_distribution: Optional[bool] = None

def extract_variables_from_text(conversation_history: str, current_known_state: dict) -> dict:
    """
    Analyzes user text contextually and extracts statistical features 
    to update our running state machine.
    """
    system_prompt = f"""
    You are a precise data extraction engine for a statistical consultation tool. 
    Analyze the incoming user conversation history. Your singular job is to look for clues that map to our statistical parameters.
    
    CRITICAL ALIGNMENT GUIDELINES:
    1. analysis_purpose: Set to 'differences' if they compare groups/treatments. Set to 'association' if they look for correlations/predictions/relationships.
    2. group_count: Set to 'two' or 'more_than_two' if groups are mentioned.
    3. data_pairing: Set to 'paired' if the same people/items are tested twice. Set to 'unpaired' if groups contain different individuals.
    4. measurement_level: Map categories/counts to 'nominal', ranked scales/likert to 'ordinal', and continuous physical scores to 'interval_ratio'.
    5. is_normal_distribution: Set to True or False only if they specify shape or normality testing.
    
    Do not guess or assume. If a variable is completely unmentioned and cannot be safely deduced, leave it as null.
    Current known baseline states: {current_known_state}
    """

    # Forced Structured Output API Call
    response = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Conversation Transcript:\n{conversation_history}"}
        ],
        response_format=ExtractedResearchState,
    )
    
    # Extract the structured data out as a native Python dictionary
    extracted_data = response.choices[0].message.parsed.model_dump()
    
    # Merge new extractions into our existing state map so we don't forget old answers
    updated_state = current_known_state.copy()
    for key, value in extracted_data.items():
        if value is not None:
            updated_state[key] = value
            
    return updated_state

def generate_conversational_response(missing_variable: str, current_state: dict) -> str:
    """
    Generates a helpful, educational follow-up question when the router flags missing details.
    """
    prompt = f"""
    You are a friendly, expert statistical consultant. We are using Sage's 'Which Stats Test' routing engine.
    The current state of our user's research metrics is: {current_state}
    
    The engine has stopped because we crucially need to know about this parameter: '{missing_variable}'
    
    Ask a natural, engaging follow-up question to discover this piece of data. 
    Briefly explain *why* this choice matters in universal language, avoiding overwhelming academic jargon.
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    
    return response.choices[0].message.content
