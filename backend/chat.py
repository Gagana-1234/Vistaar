import os
import json
import time
import hashlib
import asyncio
import logging
from groq import Groq
from dotenv import load_dotenv

from analytics import load_data, compute_summary, detect_signals
from services.cognee_service import get_relevant_context

load_dotenv()
logger = logging.getLogger(__name__)

# ── Simple in-memory response cache (survives for the server session)
_CHAT_CACHE: dict = {}
_CACHE_TTL_SECONDS = 120  # 2 minutes

GROQ_MODEL   = "groq/compound"
MAX_RETRIES  = 3
RETRY_WAIT_S = 10  # wait 10s between retries on 429


def answer_question(message: str) -> str:
    """
    Answer a merchant question using analytics data + Cognee memory.
    Uses Groq (llama-3.3-70b-versatile) — 30 req/min free tier.
    Auto-retries up to 3 times on 429. Caches for 2 minutes.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "GROQ_API_KEY not configured. Please add it to backend/.env"

    # ── Step 1: Analytics context
    df      = load_data()
    summary = compute_summary(df)
    signals = detect_signals(df)

    analytics_context = {
        "summary": summary.get("categories", {}),
        "signals": signals,
        "overall": summary.get("overall", {}),
    }

    # ── Step 2: Cache check
    cache_key = hashlib.md5(
        (message.lower().strip() + json.dumps(signals, sort_keys=True)).encode()
    ).hexdigest()
    cached = _CHAT_CACHE.get(cache_key)
    if cached and (time.time() - cached["ts"]) < _CACHE_TTL_SECONDS:
        logger.info("Chat cache hit — skipping API call")
        return cached["answer"]

    # ── Step 3: Cognee memory context
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

    # ── Step 5: Call Groq with retry on 429
    client = Groq(api_key=api_key)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            completion = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=512,
            )
            answer = completion.choices[0].message.content.strip()
            _CHAT_CACHE[cache_key] = {"answer": answer, "ts": time.time()}
            return answer

        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate" in err_str.lower() or "quota" in err_str.lower():
                if attempt < MAX_RETRIES:
                    logger.warning(f"Groq 429 — attempt {attempt}/{MAX_RETRIES}, retrying in {RETRY_WAIT_S}s...")
                    time.sleep(RETRY_WAIT_S)
                    continue
                return (
                    f"The AI is rate-limited right now (attempt {MAX_RETRIES}/{MAX_RETRIES} failed). "
                    "Please wait 30 seconds and try again."
                )
            logger.error(f"Groq chat error: {e}")
            return "Sorry, I couldn't process your question right now. Please try again."

    return "Unexpected error in chat. Please try again."

