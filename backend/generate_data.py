"""
generate_data.py — Vistaar synthetic order-level data generator.

Produces:
  data/transactions.csv  — order-level rows
  data/inventory.json    — current inventory snapshot per product

DEMO SCENARIOS embedded in the data:
  Scenario 1 — NORMAL:           Rice stays within its historical DOW-adjusted band → NO_ACTION
  Scenario 2 — SALES ANOMALY:    Beverages drop ~35% in last 14 days → HIGH_PRIORITY alert
  Scenario 3 — INVENTORY RISK:   Cooking oil demand spikes 40%+ in last 7 days while stock is low → RESTOCK alert

No real customer PII is used. customer_id values are synthetic IDs.
"""

import pandas as pd
import numpy as np
import random
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
SEED = 42
DAYS = 90                     # 90-day history window
ORDERS_PER_DAY_PER_PRODUCT = 3  # average individual orders per product per day

# Product catalogue  {product_name: (category, base_qty_per_day, unit_price_inr)}
PRODUCTS = {
    "Sunflower Oil 1L":   ("cooking_oil",  8,  120),
    "Mustard Oil 500ml":  ("cooking_oil",  7,  110),
    "Basmati Rice 5kg":   ("rice",        10,   90),
    "Sona Masoori 5kg":   ("rice",        15,   75),
    "Lay's Chips":        ("snacks",      20,   20),
    "Kurkure 90g":        ("snacks",      15,   15),
    "Amul Milk 500ml":    ("dairy",       25,   30),
    "Curd 200g":          ("dairy",       12,   25),
    "Surf Excel 1kg":     ("household",    6,   80),
    "Vim Bar":            ("household",    5,   25),
    "Frooti 200ml":       ("beverages",    8,   20),
    "Sprite 750ml":       ("beverages",   10,   45),
}

# Inventory starting quantities (units) — sized so products last the full 90 days
# Beverages and cooking_oil are intentionally given smaller buffers
# so that their anomaly scenarios (drop / spike) result in measurable stock signals.
START_INVENTORY = {
    "Sunflower Oil 1L":   360,   # ~24 days at base rate; moderate buffer
    "Mustard Oil 500ml":  330,
    "Basmati Rice 5kg":   700,
    "Sona Masoori 5kg":   900,
    "Lay's Chips":        900,
    "Kurkure 90g":        800,
    "Amul Milk 500ml":   1400,
    "Curd 200g":          700,
    "Surf Excel 1kg":     400,
    "Vim Bar":            350,
    "Frooti 200ml":      1000,   # large buffer — drop scenario shows demand fall, not stock-out
    "Sprite 750ml":      1200,
}

# Restock every 15 days (units added)
# Beverages get ZERO restock — so after ~60 days their stock starts getting lean.
# Cooking oil gets ZERO restock — so the demand spike in last 7 days causes LOW_STOCK.
RESTOCK_QTY = {
    "Sunflower Oil 1L":   100,
    "Mustard Oil 500ml":   90,
    "Basmati Rice 5kg":   200,
    "Sona Masoori 5kg":   250,
    "Lay's Chips":        350,
    "Kurkure 90g":        280,
    "Amul Milk 500ml":    500,
    "Curd 200g":          280,
    "Surf Excel 1kg":     120,
    "Vim Bar":            120,
    "Frooti 200ml":         0,   # No restock → stock slowly depletes
    "Sprite 750ml":         0,   # No restock → stock slowly depletes
}

# Reorder levels per product (units)
REORDER_LEVEL = {
    "Sunflower Oil 1L":   30,
    "Mustard Oil 500ml":  25,
    "Basmati Rice 5kg":   40,
    "Sona Masoori 5kg":   50,
    "Lay's Chips":        60,
    "Kurkure 90g":        50,
    "Amul Milk 500ml":    80,
    "Curd 200g":          40,
    "Surf Excel 1kg":     20,
    "Vim Bar":            20,
    "Frooti 200ml":       30,
    "Sprite 750ml":       35,
}

PAYMENT_METHODS = ["UPI", "Cash", "Card", "Wallet"]
DOW_FACTORS = {0: 0.85, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.05, 5: 1.25, 6: 1.25}

# Synthetic customer pool (no real PII)
CUSTOMER_POOL = [f"CUST_{i:04d}" for i in range(1, 201)]


def generate_data():
    random.seed(SEED)
    np.random.seed(SEED)

    end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=DAYS - 1)
    dates = [start_date + timedelta(days=i) for i in range(DAYS)]

    inventory = START_INVENTORY.copy()
    rows = []
    order_counter = 1

    for day_idx, date in enumerate(dates):
        dow = date.weekday()
        dow_factor = DOW_FACTORS[dow]

        # Restock every 15 days (skip day 0)
        if day_idx > 0 and day_idx % 15 == 0:
            for product in PRODUCTS:
                inventory[product] = min(
                    inventory[product] + RESTOCK_QTY[product],
                    START_INVENTORY[product] * 3  # cap at 3x start
                )

        for product, (category, base_qty, unit_price) in PRODUCTS.items():
            # ── Base daily demand with DOW factor and noise
            demand = base_qty * dow_factor * random.uniform(0.85, 1.15)

            # ── SCENARIO 2: Beverages drop ~35% in last 14 days
            if category == "beverages" and day_idx >= (DAYS - 14):
                demand *= 0.65  # 35% below normal

            # ── SCENARIO 3: Cooking oil spikes ~40% in last 7 days
            if category == "cooking_oil" and day_idx >= (DAYS - 7):
                demand *= 1.40  # 40% above normal

            # ── SCENARIO 1: Rice — no anomaly, stays within band (default)

            demand = max(1, int(demand))

            # Split daily demand into individual orders (1–4 orders per day per product)
            num_orders = random.randint(1, min(4, demand))
            qty_splits = split_into_parts(demand, num_orders)

            for qty in qty_splits:
                actual_qty = min(qty, inventory[product])
                if actual_qty <= 0:
                    continue  # out of stock, skip

                inventory[product] = max(0, inventory[product] - actual_qty)

                order_time = date + timedelta(
                    hours=random.randint(8, 20),
                    minutes=random.randint(0, 59)
                )

                rows.append({
                    "order_id": f"ORD{order_counter:06d}",
                    "transaction_id": f"TXN{uuid.UUID(int=random.getrandbits(128)).hex[:10].upper()}",
                    "date": date.strftime("%Y-%m-%d"),
                    "time": order_time.strftime("%H:%M:%S"),
                    "product": product,
                    "category": category,
                    "quantity": actual_qty,
                    "unit_price": unit_price,
                    "total_amount": actual_qty * unit_price,
                    "customer_id": random.choice(CUSTOMER_POOL),
                    "payment_method": random.choice(PAYMENT_METHODS),
                })
                order_counter += 1

    df = pd.DataFrame(rows)
    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "transactions.csv"
    df.to_csv(csv_path, index=False)

    # ── Write inventory snapshot
    inv_snapshot = []
    for product, (category, _, unit_price) in PRODUCTS.items():
        inv_snapshot.append({
            "product": product,
            "category": category,
            "current_stock": inventory[product],
            "reorder_level": REORDER_LEVEL[product],
            "unit_price": unit_price,
            "unit": "units",
        })

    inv_path = out_dir / "inventory.json"
    with open(inv_path, "w") as f:
        json.dump(inv_snapshot, f, indent=2)

    # ── Print verification summary
    print(f"[OK] Generated {len(df)} order rows over {DAYS} days.")
    print(f"   Products: {df['product'].nunique()} | Categories: {df['category'].nunique()}")
    print(f"\n-- SCENARIO VERIFICATION -------------------------------------")

    # Scenario 1 — Rice (normal)
    rice_recent = df[(df['category'] == 'rice') & (df['date'] >= (end_date - timedelta(days=7)).strftime("%Y-%m-%d"))]
    rice_hist   = df[(df['category'] == 'rice') & (df['date'] <  (end_date - timedelta(days=7)).strftime("%Y-%m-%d"))]
    r_recent_avg = rice_recent.groupby('date')['quantity'].sum().mean()
    r_hist_avg   = rice_hist.groupby('date')['quantity'].sum().mean()
    print(f"SCENARIO 1 (NORMAL)  - Rice:      hist_avg={r_hist_avg:.1f}/day  recent_avg={r_recent_avg:.1f}/day  -> expect NO_ACTION")

    # Scenario 2 — Beverages drop
    bev_recent = df[(df['category'] == 'beverages') & (df['date'] >= (end_date - timedelta(days=14)).strftime("%Y-%m-%d"))]
    bev_hist   = df[(df['category'] == 'beverages') & (df['date'] <  (end_date - timedelta(days=14)).strftime("%Y-%m-%d"))]
    b_recent_avg = bev_recent.groupby('date')['quantity'].sum().mean()
    b_hist_avg   = bev_hist.groupby('date')['quantity'].sum().mean()
    b_drop_pct   = (b_recent_avg - b_hist_avg) / b_hist_avg * 100 if b_hist_avg > 0 else 0
    print(f"SCENARIO 2 (ANOMALY) - Beverages: hist_avg={b_hist_avg:.1f}/day  recent_avg={b_recent_avg:.1f}/day  change={b_drop_pct:+.1f}%  -> expect ALERT")

    # Scenario 3 — Cooking oil spike + low stock
    oil_recent = df[(df['category'] == 'cooking_oil') & (df['date'] >= (end_date - timedelta(days=7)).strftime("%Y-%m-%d"))]
    oil_hist   = df[(df['category'] == 'cooking_oil') & (df['date'] <  (end_date - timedelta(days=7)).strftime("%Y-%m-%d"))]
    o_recent_avg = oil_recent.groupby('date')['quantity'].sum().mean()
    o_hist_avg   = oil_hist.groupby('date')['quantity'].sum().mean()
    o_spike_pct  = (o_recent_avg - o_hist_avg) / o_hist_avg * 100 if o_hist_avg > 0 else 0
    oil_stock    = sum(inventory[p] for p in PRODUCTS if PRODUCTS[p][0] == 'cooking_oil')
    coverage     = oil_stock / o_recent_avg if o_recent_avg > 0 else float('inf')
    print(f"SCENARIO 3 (RESTOCK) - Oil:       hist_avg={o_hist_avg:.1f}/day  recent_avg={o_recent_avg:.1f}/day  change={o_spike_pct:+.1f}%  stock={oil_stock}u  coverage={coverage:.1f}d  -> expect RESTOCK ALERT")
    print(f"--------------------------------------------------------------")
    print(f"\nInventory saved -> {inv_path}")
    print(f"Transactions saved -> {csv_path}")


def split_into_parts(total: int, n: int) -> list[int]:
    """Split `total` units into `n` random positive integers that sum to total."""
    if n == 1:
        return [total]
    cuts = sorted(random.sample(range(1, total), min(n - 1, total - 1)))
    parts = [cuts[0]] + [cuts[i] - cuts[i-1] for i in range(1, len(cuts))] + [total - cuts[-1]]
    return [p for p in parts if p > 0] or [total]


if __name__ == "__main__":
    generate_data()
