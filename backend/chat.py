import google.generativeai as genai
import os
import json
from dotenv import load_dotenv
from analytics import load_data, compute_summary, detect_signals

load_dotenv()

def answer_question(message: str) -> str:
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return "LLM API key not configured."
        
    df = load_data()
    summary = compute_summary(df)
    signals = detect_signals(df)
    
    context = {
        "summary": summary['categories'],
        "signals": signals
    }
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-3.6-flash')
    
    prompt = f"""
    You are an AI assistant for a store merchant.
    Use the following analytics context to answer their question.
    ONLY use the provided data. Do not invent numbers.
    Context: {json.dumps(context, indent=2)}
    
    Merchant Question: {message}
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error answering question: {str(e)}"
