import google.generativeai as genai
import os
import json
from dotenv import load_dotenv

load_dotenv()

def get_llm_analysis(signals: list, summary: dict) -> dict:
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return {'has_alert': False, 'priority': 'NONE', 'recommendation': 'LLM unavailable (no API key)', 'explanation': '', 'signals_used': []}
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-3.6-flash')
    
    prompt = f"""
    You are an AI assistant for a local kirana (grocery) store.
    Analyze the following recent signals and summary statistics.
    
    Signals: {json.dumps(signals, indent=2)}
    Summary: {json.dumps(summary['categories'], indent=2)}
    
    Task:
    1. Judge which signals are meaningful vs noise.
    2. Prioritize if multiple signals.
    3. Generate a concrete recommendation.
    4. Explain why, referencing actual numbers.
    5. If nothing significant, return 'no action needed' logic.
    
    You MUST output valid JSON ONLY, with the following keys and exact structure, and no markdown formatting or extra text outside the JSON:
    {{
      "has_alert": true or false,
      "priority": "HIGH" | "MEDIUM" | "LOW" | "NONE",
      "recommendation": "string",
      "explanation": "string",
      "signals_used": [ array of relevant signal objects ]
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith('```json'):
            text = text[7:]
        if text.startswith('```'):
            text = text[3:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()
        result = json.loads(text)
        return result
    except Exception as e:
        return {
            'has_alert': False,
            'priority': 'NONE',
            'recommendation': 'Error processing LLM response',
            'explanation': str(e),
            'signals_used': []
        }
