import json
from pathlib import Path
from datetime import datetime
from analytics import load_data, compute_summary, detect_signals
from llm_service import get_llm_analysis

NOTIFICATIONS_PATH = Path(__file__).parent / 'data' / 'notifications.json'

def load_notifications() -> list:
    if not NOTIFICATIONS_PATH.exists():
        return []
    try:
        with open(NOTIFICATIONS_PATH) as f:
            return json.load(f)
    except:
        return []

def save_notification(notification: dict):
    notifications = load_notifications()
    notifications.append(notification)
    notifications = notifications[-30:]
    NOTIFICATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(NOTIFICATIONS_PATH, 'w') as f:
        json.dump(notifications, f, indent=2, default=str)

def run_daily_check() -> dict:
    df = load_data()
    summary = compute_summary(df)
    signals = detect_signals(df)
    llm_result = get_llm_analysis(signals, summary)
    
    notification = {
        'timestamp': datetime.now().isoformat(),
        'signals_count': len(signals),
        'has_alert': llm_result.get('has_alert', False),
        'priority': llm_result.get('priority', 'NONE'),
        'recommendation': llm_result.get('recommendation', ''),
        'explanation': llm_result.get('explanation', ''),
        'signals': signals
    }
    save_notification(notification)
    return notification
