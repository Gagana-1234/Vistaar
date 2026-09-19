"""
scheduler.py — Vistaar daily check orchestrator.

Orchestration flow:
  1. Load transaction data
  2. Run analytics (compute_summary + detect_signals)
  3. Decision engine evaluates signals (deterministic, configurable thresholds)
  4. Cognee retrieves relevant merchant memory context (if available)
  5. LLM reasons using analytics + decision + cognee context
  6. Save notification to notifications.json
  7. Store the alert as a Cognee HISTORICAL_ALERT memory (so future runs can learn)

This module is called by:
  - /scheduler/run  (manual trigger from frontend or n8n)
  - Lifespan startup (auto-run if no notifications exist)
"""

import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime

from analytics import load_data, compute_summary, detect_signals
from llm_service import get_llm_analysis
from services.decision_engine import evaluate_signals
from services.cognee_service import get_relevant_context, add_merchant_memory, initialize_cognee

logger = logging.getLogger(__name__)

NOTIFICATIONS_PATH = Path(__file__).parent / "data" / "notifications.json"
MAX_NOTIFICATIONS  = 50  # Keep last 50 checks


# ═══════════════════════════════════════════════════════════════════
# NOTIFICATION PERSISTENCE
# ═══════════════════════════════════════════════════════════════════

def load_notifications() -> list:
    if not NOTIFICATIONS_PATH.exists():
        return []
    try:
        with open(NOTIFICATIONS_PATH) as f:
            return json.load(f)
    except Exception:
        return []


def save_notification(notification: dict) -> None:
    notifications = load_notifications()
    notifications.append(notification)
    notifications = notifications[-MAX_NOTIFICATIONS:]  # rolling window
    NOTIFICATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(NOTIFICATIONS_PATH, "w") as f:
        json.dump(notifications, f, indent=2, default=str)


# ═══════════════════════════════════════════════════════════════════
# MAIN DAILY CHECK
# ═══════════════════════════════════════════════════════════════════

def run_daily_check() -> dict:
    """
    Run the full Vistaar analysis pipeline and return a notification dict.

    This is the core OBSERVE → ANALYZE → REMEMBER → REASON → DECIDE → ACT loop.
    Safe to call multiple times — each call produces a new notification entry.
    """
    timestamp = datetime.now().isoformat()
    logger.info(f"🔄 Starting daily check at {timestamp}")

    # ── Step 1: Load & analyse data
    df       = load_data()
    summary  = compute_summary(df)
    signals  = detect_signals(df)
    logger.info(f"   Analytics complete — {len(signals)} signal(s) detected")

    # ── Step 2: Decision engine (deterministic rules, no LLM)
    decision = evaluate_signals(signals, summary)
    logger.info(f"   Decision engine → {decision['priority']}")

    # ── Step 3: Retrieve Cognee context (graceful — empty string if unavailable)
    cognee_context = ""
    try:
        # Build a search query based on the most prominent signal
        query = _build_cognee_query(signals, decision)
        cognee_context = asyncio.run(get_relevant_context(query))
        if cognee_context:
            logger.info(f"   Cognee returned {len(cognee_context)} chars of context")
        else:
            logger.info("   Cognee: no relevant context (or unavailable)")
    except Exception as e:
        logger.warning(f"   Cognee context retrieval failed (continuing): {e}")
        cognee_context = ""

    # ── Step 4: LLM reasoning (graceful — falls back to decision engine if LLM fails)
    llm_result = get_llm_analysis(
        signals        = signals,
        summary        = summary,
        cognee_context = cognee_context,
        decision       = decision,
    )
    logger.info(f"   LLM reasoning complete — has_alert={llm_result.get('has_alert')}")

    # ── Step 5: Build notification record
    notification = {
        "id":                     f"chk_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "timestamp":              timestamp,
        "signals_count":          len(signals),
        "has_alert":              llm_result.get("has_alert", decision.get("has_alert", False)),
        "priority":               llm_result.get("priority", decision.get("priority", "NO_ACTION")),
        "recommendation":         llm_result.get("recommendation", ""),
        "explanation":            llm_result.get("explanation", ""),
        "what_happened":          llm_result.get("what_happened", ""),
        "why_it_matters":         llm_result.get("why_it_matters", ""),
        "evidence":               llm_result.get("evidence", ""),
        "what_next":              llm_result.get("what_next", ""),
        "historical_context":     llm_result.get("historical_context_used", ""),
        "cognee_context_used":    bool(cognee_context),
        "decision_engine_output": decision,
        "signals":                signals,
        "llm_unavailable":        llm_result.get("llm_unavailable", False),
    }
    save_notification(notification)
    logger.info(f"✅ Notification saved — priority: {notification['priority']}")

    # ── Step 6: Store alert as Cognee memory (so future checks can learn from it)
    if notification["has_alert"] and notification["recommendation"]:
        try:
            memory_text = (
                f"On {timestamp[:10]}, Vistaar generated a {notification['priority']} alert: "
                f"{notification['recommendation']}. "
                f"Evidence: {notification['evidence']}"
            )
            asyncio.run(add_merchant_memory(memory_text, memory_type="HISTORICAL_ALERT"))
            logger.info("   Alert stored as Cognee HISTORICAL_ALERT memory")
        except Exception as e:
            logger.warning(f"   Could not store alert in Cognee (continuing): {e}")

    return notification


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def _build_cognee_query(signals: list, decision: dict) -> str:
    """
    Build a meaningful natural-language search query for Cognee
    based on the current signals. This ensures we retrieve the most
    relevant merchant memories.
    """
    if not signals:
        return "merchant normal sales pattern"

    # Use the highest-impact signal to anchor the query
    top_signal = signals[0]
    cat  = top_signal.get("category", "product")
    typ  = top_signal.get("signal_type", "")
    dev  = top_signal.get("deviation_pct", 0)

    if typ == "DEMAND_SPIKE":
        return f"{cat} demand increase spike sales pattern history"
    elif typ == "DEMAND_DROP":
        return f"{cat} sales decline drop pattern seasonal reason"
    elif typ == "LOW_STOCK":
        return f"{cat} restock inventory low stock historical"
    return f"{cat} sales pattern merchant context"
