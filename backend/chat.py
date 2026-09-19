import os
import json
import time
import hashlib
import asyncio
import logging
import google.generativeai as genai
from dotenv import load_dotenv

from analytics import load_data, compute_summary, detect_signals
from services.cognee_service import get_relevant_context

load_dotenv()
logger = logging.getLogger(__name__)

# ── Simple in-memory response cache (survives for the server session)
# Key: hash of (question + signals). Avoids duplicate API calls.
_CHAT_CACHE: dict = {}
_CACHE_TTL_SECONDS = 120  # cache valid for 2 minutes

GEMINI_MODEL = "gemini-3.6-flash"
MAX_RETRIES   = 3
RETRY_WAIT_S  = 15   # wait 15s between retries on 429


def answer_question(message: str) -> str:
    """
    Answer a merchant question using analytics data + Cognee memory.
    Auto-retries up to 3 times on 429 rate-limit errors (waits 15s each).
    Caches responses for 2 minutes to avoid redundant API calls.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "LLM API key not configured. Please set GEMINI_API_KEY in backend/.env"

    # ── Step 1: Analytics context
    df      = load_data()
    summary = compute_summary(df)
    signals = detect_signals(df)

    analytics_context = {
        "summary": summary.get("categories", {}),
        "signals": signals,
        "overall": summary.get("overall", {}),
    }

    # ── Step 2: Check cache before calling the API
    cache_key = hashlib.md5(
        (message.lower().strip() + json.dumps(signals, sort_keys=True)).encode()
    ).hexdigest()

    cached = _CHAT_CACHE.get(cache_key)
    if cached and (time.time() - cached["ts"]) < _CACHE_TTL_SECONDS:
        logger.info("Chat cache hit — skipping API call")
        return cached["answer"]

    # ── Step 3: Cognee memory context (graceful)
    cognee_block = ""
    try:
        cognee_ctx = asyncio.run(get_relevant_context(message))
        if cognee_ctx.strip():
            cognee_block = f"\nRELEVANT MERCHANT MEMORY:\n{cognee_ctx}\n"
    except Exception as e:
        logger.warning(f"Cognee context skipped in chat: {e}")

    # ── Step 4: Build prompt
    prompt = f"""You are Vistaar — a proactive AI Business Advisor for a small kirana merchant.

Answer the merchant's question using ONLY the data provided below.
Do NOT invent numbers. Keep your answer concise and practical.
Reference specific numbers from the data to support your answer.

ANALYTICS DATA:
{json.dumps(analytics_context, indent=2)}
{cognee_block}
MERCHANT QUESTION:
{message}
"""

    # ── Step 5: Call Gemini with retry on 429
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(GEMINI_MODEL)

    last_error = ""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = model.generate_content(prompt)
            answer = response.text.strip()
            # Cache successful response
            _CHAT_CACHE[cache_key] = {"answer": answer, "ts": time.time()}
            return answer

        except Exception as e:
            err_str = str(e)
            last_error = err_str

            if "429" in err_str or "quota" in err_str.lower() or "RESOURCE_EXHAUSTED" in err_str:
                if attempt < MAX_RETRIES:
                    logger.warning(f"Chat 429 — attempt {attempt}/{MAX_RETRIES}, retrying in {RETRY_WAIT_S}s...")
                    time.sleep(RETRY_WAIT_S)
                    continue
                else:
                    # All retries exhausted
                    return (
                        "The AI is currently rate-limited (free tier: 5 requests/minute). "
                        f"All {MAX_RETRIES} retries failed. "
                        "Please wait 1 minute and try again, or check your Gemini API billing at "
                        "https://aistudio.google.com to increase the quota."
                    )
            else:
                logger.error(f"Chat LLM error: {e}")
                return "Sorry, I couldn't process your question right now. Please try again."

    return "Unexpected error in chat. Please try again."

