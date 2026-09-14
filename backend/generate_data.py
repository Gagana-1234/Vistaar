import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
from pathlib import Path

def generate_data():
    random.seed(42)  # Reproducible results
    categories = ['cooking_oil', 'rice', 'snacks', 'dairy', 'household', 'beverages']
    base_units = {'cooking_oil': 15, 'rice': 25, 'snacks': 30, 'dairy': 20, 'household': 10, 'beverages': 18}
    base_price = {'cooking_oil': 120, 'rice': 45, 'snacks': 25, 'dairy': 60, 'household': 80, 'beverages': 35}
    # Starting inventories sized to last ~30 days at base usage; restocking every 15 days keeps them topped up
    # cooking_oil is intentionally NOT over-stocked so the last-week demand spike triggers LOW_STOCK
    start_inventory = {'cooking_oil': 450, 'rice': 800, 'snacks': 950, 'dairy': 650, 'household': 350, 'beverages': 600}
    # Restock amounts per category (applied every 15 days)
    restock_qty = {'cooking_oil': 200, 'rice': 400, 'snacks': 450, 'dairy': 320, 'household': 180, 'beverages': 300}

    end_date = datetime.now()
    start_date = end_date - timedelta(days=89)
    date_list = [start_date + timedelta(days=x) for x in range(90)]

    inventory = start_inventory.copy()
    data = []

    for i, date in enumerate(date_list):
        dow = date.weekday()
        if dow in [5, 6]:
            dow_factor = 1.25
        elif dow == 0:
            dow_factor = 0.85
        else:
            dow_factor = 1.0

        # Restock every 15 days for all categories (using per-category amounts)
        if i > 0 and i % 15 == 0:
            for cat in categories:
                inventory[cat] += restock_qty[cat]

        for cat in categories:
            units = base_units[cat] * dow_factor * random.uniform(0.85, 1.15)
            
            # Deliberate anomaly: cooking_oil demand spikes +40% in last 7 days
            # Combined with no extra restock in that window → inventory runs critically low
            if i >= 83 and cat == 'cooking_oil':
                units *= 1.40
            
            units = int(units)
            
            actual_sold = min(units, inventory[cat])
            inventory[cat] = max(0, inventory[cat] - actual_sold)
            revenue = actual_sold * base_price[cat]
            
            data.append({
                'date': date.strftime('%Y-%m-%d'),
                'category': cat,
                'units_sold': actual_sold,
                'revenue': revenue,
                'inventory': inventory[cat]
            })

    df = pd.DataFrame(data)
    out_dir = Path(__file__).parent / 'data'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / 'transactions.csv'
    df.to_csv(out_path, index=False)
    
    # Verify anomaly is present
    print("Data generation complete. Checking cooking_oil (last 14 days):")
    oil_df = df[df['category'] == 'cooking_oil'].tail(14)
    print(oil_df[['date', 'units_sold', 'inventory']].to_string())
    print(f"\nFinal cooking_oil inventory : {inventory['cooking_oil']} units")
    oil_recent = df[df['category'] == 'cooking_oil'].tail(7)
    velocity = oil_recent['units_sold'].mean()
    coverage = inventory['cooking_oil'] / velocity if velocity > 0 else float('inf')
    print(f"Last-7d avg velocity        : {velocity:.1f} units/day")
    print(f"Stock coverage              : {coverage:.1f} days  (< 7 = LOW_STOCK alert)")

if __name__ == '__main__':
    generate_data()
