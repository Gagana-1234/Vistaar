import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

DATA_PATH = Path(__file__).parent / 'data' / 'transactions.csv'

def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, parse_dates=['date'])
    return df

def compute_summary(df: pd.DataFrame) -> dict:
    end_date = df['date'].max()
    start_30d = end_date - timedelta(days=29)
    start_7d = end_date - timedelta(days=6)
    start_prior7d = end_date - timedelta(days=13)
    end_prior7d = end_date - timedelta(days=7)

    summary = {'categories': {}, 'overall': {}}
    categories = df['category'].unique()

    df_30d = df[df['date'] >= start_30d]
    df_7d = df[df['date'] >= start_7d]
    df_prior7d = df[(df['date'] >= start_prior7d) & (df['date'] <= end_prior7d)]

    total_revenue_overall = 0
    total_units_7d = 0

    for cat in categories:
        cat_30d = df_30d[df_30d['category'] == cat]
        cat_7d = df_7d[df_7d['category'] == cat]
        cat_prior7d = df_prior7d[df_prior7d['category'] == cat]

        rev_30d = float(cat_30d['revenue'].sum())
        units_7d = float(cat_7d['units_sold'].sum())
        units_prior7d = float(cat_prior7d['units_sold'].sum())
        
        growth = ((units_7d - units_prior7d) / units_prior7d * 100) if units_prior7d > 0 else 0
        velocity = units_7d / 7.0
        
        latest_inv = 0
        if not cat_30d.empty:
            latest_inv = float(cat_30d.sort_values('date').iloc[-1]['inventory'])
            
        coverage = latest_inv / velocity if velocity > 0 else float('inf')
        rolling7_avg = velocity

        summary['categories'][cat] = {
            'total_revenue_30d': rev_30d,
            'units_sold_7d': units_7d,
            'units_sold_prior7d': units_prior7d,
            'growth_pct': growth,
            'velocity': velocity,
            'current_inventory': latest_inv,
            'stock_coverage_days': coverage,
            'rolling7_avg': rolling7_avg
        }

        total_revenue_overall += rev_30d
        total_units_7d += units_7d

    summary['overall'] = {
        'total_revenue_30d': total_revenue_overall,
        'units_sold_7d': total_units_7d
    }

    daily_rev = df_30d.groupby('date')['revenue'].sum().reset_index()
    summary['chart_data'] = [{'date': row['date'].strftime('%Y-%m-%d'), 'revenue': float(row['revenue'])} for _, row in daily_rev.iterrows()]

    return summary

def compute_dow_baselines(df: pd.DataFrame) -> dict:
    end_date = df['date'].max()
    cutoff_date = end_date - timedelta(days=7)
    historical_df = df[df['date'] <= cutoff_date].copy()
    historical_df['dow'] = historical_df['date'].dt.dayofweek

    baselines = {}
    for cat in df['category'].unique():
        cat_df = historical_df[historical_df['category'] == cat]
        avg_by_dow = cat_df.groupby('dow')['units_sold'].mean().to_dict()
        baselines[cat] = {i: float(avg_by_dow.get(i, 0)) for i in range(7)}
    return baselines

def detect_signals(df: pd.DataFrame) -> list:
    baselines = compute_dow_baselines(df)
    end_date = df['date'].max()
    start_7d = end_date - timedelta(days=6)
    recent_df = df[df['date'] >= start_7d].copy()
    recent_df['dow'] = recent_df['date'].dt.dayofweek

    signals = []
    
    for cat in df['category'].unique():
        cat_recent = recent_df[recent_df['category'] == cat]
        actual_total = 0
        expected_total = 0
        
        for _, row in cat_recent.iterrows():
            actual_total += row['units_sold']
            expected_total += baselines[cat][row['dow']]
            
        actual_avg = actual_total / 7.0
        expected_avg = expected_total / 7.0
        
        deviation = ((actual_avg - expected_avg) / expected_avg * 100) if expected_avg > 0 else 0
        
        latest_row = cat_recent.sort_values('date').iloc[-1]
        latest_inv = latest_row['inventory']
        velocity = actual_avg
        coverage = latest_inv / velocity if velocity > 0 else float('inf')
        
        if abs(deviation) > 20:
            sig_type = 'DEMAND_SPIKE' if deviation > 0 else 'DEMAND_DROP'
            signals.append({
                'category': cat,
                'signal_type': sig_type,
                'deviation_pct': float(deviation),
                'actual_avg_units': float(actual_avg),
                'expected_avg_units': float(expected_avg),
                'current_inventory': int(latest_inv),
                'stock_coverage_days': float(coverage),
                'velocity': float(velocity),
                'description': f"{sig_type}: {cat} volume is {deviation:.1f}% vs historical."
            })
            
        if coverage < 7:
            signals.append({
                'category': cat,
                'signal_type': 'LOW_STOCK',
                'deviation_pct': 0.0,
                'actual_avg_units': float(actual_avg),
                'expected_avg_units': float(expected_avg),
                'current_inventory': int(latest_inv),
                'stock_coverage_days': float(coverage),
                'velocity': float(velocity),
                'description': f"LOW_STOCK: {cat} has only {coverage:.1f} days of inventory left."
            })

    signals.sort(key=lambda x: abs(x['deviation_pct']) if x['signal_type'] != 'LOW_STOCK' else float('inf'), reverse=True)
    return signals

def get_chart_data(df: pd.DataFrame) -> list:
    end_date = df['date'].max()
    start_30d = end_date - timedelta(days=29)
    df_30d = df[df['date'] >= start_30d]
    
    chart_data = []
    dates = sorted(df_30d['date'].unique())
    
    for d in dates:
        day_df = df_30d[df_30d['date'] == d]
        entry = {
            'date': pd.Timestamp(d).strftime('%Y-%m-%d'),
            'revenue': float(day_df['revenue'].sum())
        }
        for _, row in day_df.iterrows():
            entry[row['category']] = float(row['revenue'])
        chart_data.append(entry)
        
    return chart_data
