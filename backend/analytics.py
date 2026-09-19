"""
analytics.py — Vistaar backend analytics engine.

Reads order-level transactions.csv and produces:
  - Category/product summaries
  - Merchant-specific DOW baselines (learned from historical data)
  - Demand signals (spikes, drops, low stock)
  - Structured alerts payload for n8n + AI reasoning

Key principle: ALL numerical facts are computed here.
The LLM receives pre-computed numbers — it never invents metrics.
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

DATA_PATH = Path(__file__).parent / "data" / "transactions.csv"
INVENTORY_PATH = Path(__file__).parent / "data" / "inventory.json"


# ═══════════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════

def load_data() -> pd.DataFrame:
    """Load order-level transactions and return a clean DataFrame."""
    df = pd.read_csv(DATA_PATH, parse_dates=["date"])
    # Ensure numeric columns are correct types
    for col in ["quantity", "unit_price", "total_amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def get_inventory() -> list[dict]:
    """Load inventory snapshot from inventory.json."""
    if not INVENTORY_PATH.exists():
        return []
    try:
        with open(INVENTORY_PATH) as f:
            return json.load(f)
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════
# AGGREGATION HELPERS
# ═══════════════════════════════════════════════════════════════════

def _aggregate_to_category_day(df: pd.DataFrame) -> pd.DataFrame:
    """
    Collapse order-level rows to one row per (date, category).
    This is the internal working format for all analytics.
    """
    agg = (
        df.groupby(["date", "category"])
        .agg(
            units_sold=("quantity", "sum"),
            revenue=("total_amount", "sum"),
            transaction_count=("order_id", "nunique"),
        )
        .reset_index()
    )
    return agg


def _aggregate_to_product_day(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse order-level rows to one row per (date, product, category)."""
    agg = (
        df.groupby(["date", "product", "category"])
        .agg(
            units_sold=("quantity", "sum"),
            revenue=("total_amount", "sum"),
        )
        .reset_index()
    )
    return agg


# ═══════════════════════════════════════════════════════════════════
# MERCHANT-SPECIFIC DOW BASELINES
# ═══════════════════════════════════════════════════════════════════

def compute_dow_baselines(df: pd.DataFrame) -> dict:
    """
    Learn the merchant's normal DOW (day-of-week) sales pattern
    from all data *except* the most recent 7 days.

    Returns: {category: {dow_int: avg_units_per_day}}
    This is the merchant-specific normal — NOT a global threshold.
    """
    agg = _aggregate_to_category_day(df)
    end_date = agg["date"].max()
    cutoff = end_date - timedelta(days=7)
    historical = agg[agg["date"] <= cutoff].copy()
    historical["dow"] = historical["date"].dt.dayofweek

    baselines: dict = {}
    for cat in agg["category"].unique():
        cat_df = historical[historical["category"] == cat]
        avg_by_dow = cat_df.groupby("dow")["units_sold"].mean().to_dict()
        baselines[cat] = {i: float(avg_by_dow.get(i, 0)) for i in range(7)}
    return baselines


def compute_merchant_profile(df: pd.DataFrame) -> dict:
    """
    Compute the merchant's normal business profile:
      - DOW baselines per category
      - Weekly revenue mean ± std (from historical data)
      - Average transaction value
    """
    agg = _aggregate_to_category_day(df)
    end_date = agg["date"].max()
    cutoff = end_date - timedelta(days=14)
    hist = agg[agg["date"] <= cutoff]

    # Weekly revenue buckets
    hist_copy = hist.copy()
    hist_copy["week"] = hist_copy["date"].dt.isocalendar().week
    weekly_rev = hist_copy.groupby("week")["revenue"].sum()

    # Average transaction value from raw data
    raw_end = df["date"].max()
    raw_cutoff = raw_end - timedelta(days=14)
    hist_raw = df[df["date"] <= raw_cutoff]
    avg_txn_value = float(hist_raw["total_amount"].mean()) if not hist_raw.empty else 0.0

    return {
        "dow_baselines": compute_dow_baselines(df),
        "weekly_revenue_mean": float(weekly_rev.mean()) if not weekly_rev.empty else 0.0,
        "weekly_revenue_std": float(weekly_rev.std()) if not weekly_rev.empty else 0.0,
        "avg_transaction_value": round(avg_txn_value, 2),
        "data_window_days": int((df["date"].max() - df["date"].min()).days),
    }


# ═══════════════════════════════════════════════════════════════════
# SUMMARY (used by existing /analytics/summary endpoint)
# ═══════════════════════════════════════════════════════════════════

def compute_summary(df: pd.DataFrame) -> dict:
    """
    Compute 7d / 30d summary per category.
    Preserves the original API contract consumed by the frontend.
    """
    agg = _aggregate_to_category_day(df)
    inv_data = get_inventory()
    inv_by_cat: dict[str, int] = {}
    for item in inv_data:
        cat = item["category"]
        inv_by_cat[cat] = inv_by_cat.get(cat, 0) + item["current_stock"]

    end_date = agg["date"].max()
    start_30d = end_date - timedelta(days=29)
    start_7d = end_date - timedelta(days=6)
    start_prior7d = end_date - timedelta(days=13)
    end_prior7d = end_date - timedelta(days=7)

    df_30d = agg[agg["date"] >= start_30d]
    df_7d = agg[agg["date"] >= start_7d]
    df_prior7d = agg[(agg["date"] >= start_prior7d) & (agg["date"] <= end_prior7d)]

    summary: dict = {"categories": {}, "overall": {}}
    total_revenue_overall = 0.0
    total_units_7d = 0.0

    for cat in agg["category"].unique():
        cat_30d = df_30d[df_30d["category"] == cat]
        cat_7d = df_7d[df_7d["category"] == cat]
        cat_prior7d = df_prior7d[df_prior7d["category"] == cat]

        rev_30d = float(cat_30d["revenue"].sum())
        units_7d = float(cat_7d["units_sold"].sum())
        units_prior7d = float(cat_prior7d["units_sold"].sum())

        growth = (
            (units_7d - units_prior7d) / units_prior7d * 100
            if units_prior7d > 0
            else 0.0
        )
        velocity = units_7d / 7.0

        # Use inventory.json current stock (more accurate than running balance)
        current_inventory = inv_by_cat.get(cat, 0)
        coverage = current_inventory / velocity if velocity > 0 else float("inf")

        summary["categories"][cat] = {
            "total_revenue_30d": round(rev_30d, 2),
            "units_sold_7d": round(units_7d, 2),
            "units_sold_prior7d": round(units_prior7d, 2),
            "growth_pct": round(growth, 2),
            "velocity": round(velocity, 2),
            "current_inventory": current_inventory,
            "stock_coverage_days": round(coverage, 1) if coverage != float("inf") else 9999,
            "rolling7_avg": round(velocity, 2),
        }

        total_revenue_overall += rev_30d
        total_units_7d += units_7d

    summary["overall"] = {
        "total_revenue_30d": round(total_revenue_overall, 2),
        "units_sold_7d": round(total_units_7d, 2),
    }

    daily_rev = df_30d.groupby("date")["revenue"].sum().reset_index()
    summary["chart_data"] = [
        {"date": row["date"].strftime("%Y-%m-%d"), "revenue": float(row["revenue"])}
        for _, row in daily_rev.iterrows()
    ]

    return summary


# ═══════════════════════════════════════════════════════════════════
# SIGNAL DETECTION
# ═══════════════════════════════════════════════════════════════════

def detect_signals(df: pd.DataFrame) -> list[dict]:
    """
    Compare recent 7-day actuals against merchant-specific DOW baselines.
    Returns a list of signal dicts — no LLM involved, purely deterministic.
    """
    baselines = compute_dow_baselines(df)
    agg = _aggregate_to_category_day(df)
    inv_data = get_inventory()
    inv_by_cat: dict[str, int] = {}
    for item in inv_data:
        cat = item["category"]
        inv_by_cat[cat] = inv_by_cat.get(cat, 0) + item["current_stock"]

    end_date = agg["date"].max()
    start_7d = end_date - timedelta(days=6)
    recent = agg[agg["date"] >= start_7d].copy()
    recent["dow"] = recent["date"].dt.dayofweek

    signals: list[dict] = []

    for cat in agg["category"].unique():
        cat_recent = recent[recent["category"] == cat]
        if cat_recent.empty:
            continue

        actual_total = 0.0
        expected_total = 0.0
        for _, row in cat_recent.iterrows():
            actual_total += row["units_sold"]
            expected_total += baselines[cat][row["dow"]]

        actual_avg = actual_total / 7.0
        expected_avg = expected_total / 7.0

        deviation = (
            (actual_avg - expected_avg) / expected_avg * 100
            if expected_avg > 0
            else 0.0
        )

        current_inventory = inv_by_cat.get(cat, 0)
        velocity = actual_avg
        coverage = current_inventory / velocity if velocity > 0 else float("inf")

        # Demand spike or drop signal
        if abs(deviation) > 20:
            sig_type = "DEMAND_SPIKE" if deviation > 0 else "DEMAND_DROP"
            signals.append({
                "category": cat,
                "signal_type": sig_type,
                "deviation_pct": round(deviation, 1),
                "actual_avg_units": round(actual_avg, 1),
                "expected_avg_units": round(expected_avg, 1),
                "current_inventory": current_inventory,
                "stock_coverage_days": round(coverage, 1) if coverage != float("inf") else 9999,
                "velocity": round(velocity, 1),
                "description": (
                    f"{sig_type}: {cat} volume is {deviation:+.1f}% vs merchant historical baseline."
                ),
            })

        # Low stock signal (independent of demand deviation)
        if coverage < 7:
            signals.append({
                "category": cat,
                "signal_type": "LOW_STOCK",
                "deviation_pct": 0.0,
                "actual_avg_units": round(actual_avg, 1),
                "expected_avg_units": round(expected_avg, 1),
                "current_inventory": current_inventory,
                "stock_coverage_days": round(coverage, 1),
                "velocity": round(velocity, 1),
                "description": (
                    f"LOW_STOCK: {cat} has only {coverage:.1f} days of inventory at current velocity."
                ),
            })

    # Sort: highest-impact signals first; LOW_STOCK always floats to top
    signals.sort(
        key=lambda x: (
            float("inf") if x["signal_type"] == "LOW_STOCK" else abs(x["deviation_pct"])
        ),
        reverse=True,
    )
    return signals


# ═══════════════════════════════════════════════════════════════════
# CHART DATA (used by existing /analytics/chart endpoint)
# ═══════════════════════════════════════════════════════════════════

def get_chart_data(df: pd.DataFrame) -> list[dict]:
    """Return daily revenue per category for the last 30 days (chart payload)."""
    agg = _aggregate_to_category_day(df)
    end_date = agg["date"].max()
    start_30d = end_date - timedelta(days=29)
    df_30d = agg[agg["date"] >= start_30d]

    chart_data: list[dict] = []
    for d in sorted(df_30d["date"].unique()):
        day_df = df_30d[df_30d["date"] == d]
        entry: dict = {"date": pd.Timestamp(d).strftime("%Y-%m-%d"), "revenue": 0.0}
        for _, row in day_df.iterrows():
            entry[row["category"]] = float(row["revenue"])
            entry["revenue"] += float(row["revenue"])
        chart_data.append(entry)

    return chart_data


# ═══════════════════════════════════════════════════════════════════
# ALERTS PAYLOAD (used by n8n via /analytics/alerts)
# ═══════════════════════════════════════════════════════════════════

def get_alerts_data(df: pd.DataFrame) -> dict:
    """
    Return the full structured payload that n8n uses to orchestrate the workflow:
      - signals detected
      - summary per category
      - merchant profile (baselines, normal ranges)
      - inventory snapshot
    This is the single source of truth that flows into Cognee + AI reasoning.
    """
    signals = detect_signals(df)
    summary = compute_summary(df)
    profile = compute_merchant_profile(df)
    inventory = get_inventory()

    return {
        "merchant_id": "MERCHANT_001",  # In production: from auth context
        "timestamp": datetime.now().isoformat(),
        "signals": signals,
        "summary": summary["categories"],
        "overall": summary["overall"],
        "merchant_profile": profile,
        "inventory": inventory,
    }
