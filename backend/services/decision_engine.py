"""
services/decision_engine.py — Vistaar decision layer.

Sits between analytics and AI. Applies configurable, deterministic
rules to produce a priority decision BEFORE the LLM is called.

This means:
  - Priority thresholds are NOT hardcoded magic numbers buried in prompts
  - Rules can be tuned via environment variables without touching code
  - The LLM receives the decision as additional context (can agree/disagree)

PRIORITY LEVELS:
  NO_ACTION    — All metrics within merchant's normal range
  LOW          — Minor deviation, informational only
  MEDIUM       — Notable deviation, merchant should review
  HIGH         — Significant deviation, action recommended soon

DECISION OUTPUTS:
  {
    "priority": "NO_ACTION" | "LOW" | "MEDIUM" | "HIGH",
    "action":   "NO_ACTION" | "MONITOR" | "REVIEW" | "RESTOCK" | "INVESTIGATE",
    "reasons":  [list of human-readable reasoning strings],
    "signals_used": [list of signal dicts that triggered the decision]
  }
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ── Configurable thresholds (all overridable via environment variables)
SPIKE_HIGH_PCT     = float(os.getenv("ALERT_PRIORITY_SPIKE_HIGH",    "30"))  # % demand spike → HIGH
SPIKE_MEDIUM_PCT   = float(os.getenv("ALERT_PRIORITY_SPIKE_MEDIUM",  "20"))  # % demand spike → MEDIUM
DROP_HIGH_PCT      = float(os.getenv("ALERT_PRIORITY_DROP_HIGH",     "30"))  # % demand drop → HIGH
DROP_MEDIUM_PCT    = float(os.getenv("ALERT_PRIORITY_DROP_MEDIUM",   "20"))  # % demand drop → MEDIUM
COVERAGE_HIGH_DAYS = float(os.getenv("ALERT_COVERAGE_DAYS_HIGH",      "3"))  # stock days < this → HIGH
COVERAGE_MED_DAYS  = float(os.getenv("ALERT_COVERAGE_DAYS_MEDIUM",    "7"))  # stock days < this → MEDIUM


# ═══════════════════════════════════════════════════════════════════
# MAIN DECISION FUNCTION
# ═══════════════════════════════════════════════════════════════════

def evaluate_signals(signals: list[dict], summary: dict | None = None) -> dict:
    """
    Apply business rules to detected signals and produce a priority decision.

    Args:
        signals: Output of analytics.detect_signals()
        summary: Optional output of analytics.compute_summary() (for context)

    Returns:
        {
            "priority":     str,
            "action":       str,
            "has_alert":    bool,
            "reasons":      list[str],
            "signals_used": list[dict],
        }
    """
    if not signals:
        return _decision("NO_ACTION", "NO_ACTION", ["No unusual signals detected."], [])

    priority_scores: list[tuple[int, str, str, dict]] = []  # (score, priority, action, signal)

    for sig in signals:
        sig_type  = sig.get("signal_type", "")
        deviation = abs(sig.get("deviation_pct", 0.0))
        coverage  = sig.get("stock_coverage_days", 9999)
        category  = sig.get("category", "?")

        # ── LOW_STOCK rules
        if sig_type == "LOW_STOCK":
            if coverage <= COVERAGE_HIGH_DAYS:
                reason = (
                    f"{category}: only {coverage:.1f} days of stock remaining "
                    f"at current demand velocity. Immediate restock recommended."
                )
                priority_scores.append((4, "HIGH", "RESTOCK", sig, reason))
            elif coverage <= COVERAGE_MED_DAYS:
                reason = (
                    f"{category}: {coverage:.1f} days of stock remaining. "
                    f"Consider restocking within the next few days."
                )
                priority_scores.append((2, "MEDIUM", "RESTOCK", sig, reason))

        # ── DEMAND_SPIKE rules
        elif sig_type == "DEMAND_SPIKE":
            if deviation >= SPIKE_HIGH_PCT:
                reason = (
                    f"{category}: demand is {deviation:.1f}% above merchant's normal baseline "
                    f"(actual {sig.get('actual_avg_units',0):.1f} vs expected "
                    f"{sig.get('expected_avg_units',0):.1f} units/day)."
                )
                priority_scores.append((3, "HIGH", "INVESTIGATE", sig, reason))
            elif deviation >= SPIKE_MEDIUM_PCT:
                reason = (
                    f"{category}: demand is {deviation:.1f}% above normal. "
                    f"Monitor closely."
                )
                priority_scores.append((2, "MEDIUM", "MONITOR", sig, reason))
            else:
                reason = f"{category}: minor demand increase ({deviation:.1f}%), within normal variance."
                priority_scores.append((1, "LOW", "MONITOR", sig, reason))

        # ── DEMAND_DROP rules
        elif sig_type == "DEMAND_DROP":
            if deviation >= DROP_HIGH_PCT:
                reason = (
                    f"{category}: demand dropped {deviation:.1f}% below merchant's normal baseline "
                    f"(actual {sig.get('actual_avg_units',0):.1f} vs expected "
                    f"{sig.get('expected_avg_units',0):.1f} units/day). "
                    f"Investigate potential causes."
                )
                priority_scores.append((3, "HIGH", "INVESTIGATE", sig, reason))
            elif deviation >= DROP_MEDIUM_PCT:
                reason = (
                    f"{category}: demand dropped {deviation:.1f}% below normal. "
                    f"Review for seasonal or competitor impact."
                )
                priority_scores.append((2, "MEDIUM", "REVIEW", sig, reason))
            else:
                reason = f"{category}: minor demand drop ({deviation:.1f}%), within normal variance."
                priority_scores.append((1, "LOW", "MONITOR", sig, reason))

    if not priority_scores:
        return _decision("NO_ACTION", "NO_ACTION", ["All signals are within acceptable ranges."], [])

    # Select highest-priority decision
    priority_scores.sort(key=lambda x: x[0], reverse=True)
    top_score, top_priority, top_action, _, _ = priority_scores[0]

    reasons      = [item[4] for item in priority_scores]
    signals_used = [item[3] for item in priority_scores]

    return _decision(top_priority, top_action, reasons, signals_used)


def _decision(priority: str, action: str, reasons: list[str], signals_used: list[dict]) -> dict:
    """Helper to build a standardised decision dict."""
    return {
        "priority":     priority,
        "action":       action,
        "has_alert":    priority not in ("NO_ACTION", "LOW"),
        "reasons":      reasons,
        "signals_used": signals_used,
        "thresholds_used": {
            "spike_high_pct":     SPIKE_HIGH_PCT,
            "spike_medium_pct":   SPIKE_MEDIUM_PCT,
            "drop_high_pct":      DROP_HIGH_PCT,
            "coverage_high_days": COVERAGE_HIGH_DAYS,
            "coverage_med_days":  COVERAGE_MED_DAYS,
        },
    }


# ═══════════════════════════════════════════════════════════════════
# PRIORITY COLOUR MAPPING (used by frontend)
# ═══════════════════════════════════════════════════════════════════

PRIORITY_EMOJI = {
    "HIGH":      "⚠️",
    "MEDIUM":    "🔔",
    "LOW":       "ℹ️",
    "NO_ACTION": "✅",
}

PRIORITY_LABEL = {
    "HIGH":      "High Priority",
    "MEDIUM":    "Medium Priority",
    "LOW":       "Low Priority",
    "NO_ACTION": "All Clear",
}
