import os
import json
import logging
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

GROQ_MODEL = "groq/compound"


def get_llm_analysis(
    signals: list,
    summary: dict,
    cognee_context: str = "",
    decision: dict | None = None,
) -> dict:
    """
    Call Groq (llama-3.3-70b-versatile) to reason about the current business situation.

    Args:
        signals:        List of signal dicts from analytics.detect_signals()
        summary:        Category summary dict from analytics.compute_summary()
        cognee_context: Relevant merchant memories from Cognee (empty str if unavailable)
        decision:       Pre-computed decision from decision_engine.evaluate_signals()

    Returns dict with keys:
        has_alert, priority, recommendation, explanation,
        what_happened, why_it_matters, evidence, what_next,
        historical_context_used, signals_used
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.warning("GROQ_API_KEY not set — LLM analysis skipped.")
        return _fallback_result(
            decision, "LLM unavailable (GROQ_API_KEY not set). Showing analytics result."
        )


    # ── Build cognee context block for prompt
    cognee_block = ""
    if cognee_context.strip():
        cognee_block = f"""
RELEVANT MERCHANT MEMORY (from Cognee — use this to contextualise your reasoning):
{cognee_context}
"""

    # ── Build decision context block
    decision_block = ""
    if decision:
        decision_block = f"""
PRE-COMPUTED DECISION (from deterministic rules engine):
  Priority: {decision.get('priority', 'UNKNOWN')}
  Recommended action: {decision.get('action', 'UNKNOWN')}
  Rule-based reasons: {json.dumps(decision.get('reasons', []), indent=2)}
"""

    # ── Construct the full reasoning prompt
    prompt = f"""You are Vistaar — an AI Business Advisor for a small kirana (grocery) merchant.

You must reason about the merchant's business situation using ONLY the data provided below.
Do NOT invent numbers. All metrics are pre-calculated by the analytics engine.

══════════════════════════════════════════════════════════════════
ANALYTICS DATA (source of truth — backend calculated)
══════════════════════════════════════════════════════════════════
SIGNALS DETECTED:
{json.dumps(signals, indent=2)}

CATEGORY SUMMARY (last 7d / 30d):
{json.dumps(summary.get('categories', summary), indent=2)}
{cognee_block}
{decision_block}
══════════════════════════════════════════════════════════════════
YOUR TASK:
══════════════════════════════════════════════════════════════════
1. Decide if any signal deserves the merchant's attention.
2. Use Cognee merchant memory (if provided) to check if the situation is already explained by historical context.
   - If a memory explains the signal (e.g. "Monday is always slow"), downgrade the urgency accordingly.
3. Generate a clear, actionable recommendation.
4. Explain your reasoning in plain language a small merchant can understand.

OUTPUT FORMAT — return ONLY valid JSON with EXACTLY these keys:
{{
  "has_alert": true or false,
  "priority": "HIGH" | "MEDIUM" | "LOW" | "NO_ACTION",
  "recommendation": "One clear sentence telling the merchant what to do",
  "explanation": "2–3 sentences explaining why this matters",
  "what_happened": "Brief factual description of what the data shows",
  "why_it_matters": "Why this could impact the merchant's business",
  "evidence": "Key numbers from the analytics data that support this",
  "what_next": "Concrete next step for the merchant",
  "historical_context_used": "Which memory/context from Cognee influenced your reasoning, or 'None' if not applicable",
  "signals_used": [ array of the signal objects that most influenced your decision ]
}}

Do not add any text before or after the JSON block.
"""

    try:
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1024,
        )
        text = completion.choices[0].message.content.strip()

        # Strip markdown code fences if present
        for fence in ("```json", "```"):
            if text.startswith(fence):
                text = text[len(fence):]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        result = json.loads(text)

        # Ensure all expected keys are present (defensive)
        for key in ("has_alert", "priority", "recommendation", "explanation",
                    "what_happened", "why_it_matters", "evidence", "what_next",
                    "historical_context_used", "signals_used"):
            if key not in result:
                result[key] = "" if key != "signals_used" else []

        logger.info(f"🤖 LLM analysis complete — priority: {result.get('priority')}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"LLM returned invalid JSON: {e}")
        return _fallback_result(decision, f"LLM returned malformed JSON: {str(e)}")
    except Exception as e:
        logger.error(f"LLM API call failed: {e}")
        return _fallback_result(decision, f"LLM API error: {str(e)}")


def _fallback_result(decision: dict | None, reason: str) -> dict:
    """
    Return a safe fallback result based on the deterministic decision engine
    when the LLM is unavailable. The dashboard still shows the analytics result.
    """
    if decision:
        reasons_text = " | ".join(decision.get("reasons", []))
        return {
            "has_alert":                decision.get("has_alert", False),
            "priority":                 decision.get("priority", "NO_ACTION"),
            "recommendation":           f"[Analytics only] {decision.get('action', 'No action')}",
            "explanation":              reasons_text or "See analytics data.",
            "what_happened":            reasons_text,
            "why_it_matters":           "Review the analytics data for details.",
            "evidence":                 "Based on backend analytics (AI reasoning unavailable).",
            "what_next":                decision.get("action", "Review your data."),
            "historical_context_used":  "None (AI unavailable)",
            "signals_used":             decision.get("signals_used", []),
            "llm_unavailable":          True,
            "llm_unavailable_reason":   reason,
        }
    return {
        "has_alert":                False,
        "priority":                 "NO_ACTION",
        "recommendation":           "Analytics complete. AI reasoning unavailable.",
        "explanation":              reason,
        "what_happened":            "",
        "why_it_matters":           "",
        "evidence":                 "",
        "what_next":                "",
        "historical_context_used":  "None",
        "signals_used":             [],
        "llm_unavailable":          True,
        "llm_unavailable_reason":   reason,
    }
