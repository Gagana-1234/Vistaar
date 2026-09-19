"""
main.py — Vistaar FastAPI backend entry point.

API endpoints:

  Existing (preserved):
    GET  /                          — health check
    GET  /analytics/summary         — 7d/30d summary per category
    GET  /analytics/signals         — detected demand/stock signals
    GET  /analytics/chart           — daily revenue data for chart
    POST /scheduler/run             — run full daily check pipeline
    GET  /scheduler/history         — list past notifications
    POST /chat                      — conversational Q&A

  New (n8n + Cognee integration):
    GET  /analytics/alerts          — full alerts payload for n8n
    GET  /analytics/inventory       — inventory snapshot
    GET  /analytics/merchant-profile — DOW baselines + normal ranges
    POST /cognee/add-memory         — store a merchant memory in Cognee
    GET  /cognee/search             — search Cognee merchant memory
    POST /cognee/seed               — seed demo memories into Cognee
    GET  /cognee/status             — Cognee availability status
    POST /alerts/receive            — n8n posts completed alert here
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from analytics import load_data, compute_summary, detect_signals, get_chart_data, get_alerts_data, get_inventory
from scheduler import run_daily_check, load_notifications, save_notification
from chat import answer_question
from services.cognee_service import (
    add_merchant_memory,
    search_merchant_memory,
    seed_demo_memories,
    get_cognee_status,
    initialize_cognee,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger(__name__)

# ── Ensure data directory and initial data exist
data_dir = Path(__file__).parent / "data"
data_dir.mkdir(parents=True, exist_ok=True)
if not (data_dir / "transactions.csv").exists():
    from generate_data import generate_data
    generate_data()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise optional services without blocking API startup."""
    logger.info("🚀 Vistaar API starting up...")
    initialize_cognee()
    logger.info("   Startup complete.")
    yield
    logger.info("🛑 Vistaar API shutting down.")


app = FastAPI(title="Vistaar API — AI Business Advisor", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════
# REQUEST / RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str

class MemoryRequest(BaseModel):
    text: str
    memory_type: str = "MERCHANT_CONTEXT"
    merchant_id: str = "MERCHANT_001"

class AlertReceiveRequest(BaseModel):
    """Payload posted by n8n when it completes a workflow run."""
    source:          str = "n8n"
    workflow_id:     str = ""
    priority:        str = "NO_ACTION"
    has_alert:       bool = False
    recommendation:  str = ""
    explanation:     str = ""
    what_happened:   str = ""
    why_it_matters:  str = ""
    evidence:        str = ""
    what_next:       str = ""
    historical_context: str = ""
    signals:         list = []


# ═══════════════════════════════════════════════════════════════════
# HEALTH
# ═══════════════════════════════════════════════════════════════════

@app.get("/")
def read_root():
    return {
        "message": "Vistaar API",
        "version": "2.0.0",
        "status":  "ok",
        "cognee":  get_cognee_status()["available"],
    }


# ═══════════════════════════════════════════════════════════════════
# ANALYTICS ENDPOINTS (existing + new)
# ═══════════════════════════════════════════════════════════════════

@app.get("/analytics/summary")
def analytics_summary():
    try:
        df = load_data()
        return compute_summary(df)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/signals")
def analytics_signals():
    try:
        df = load_data()
        return {"signals": detect_signals(df)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/chart")
def analytics_chart():
    try:
        df = load_data()
        return get_chart_data(df)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/inventory")
def analytics_inventory():
    """Return current inventory snapshot (from inventory.json)."""
    try:
        return {"inventory": get_inventory()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/merchant-profile")
def analytics_merchant_profile():
    """Return merchant-specific normal ranges (DOW baselines etc.)."""
    try:
        from analytics import compute_merchant_profile
        df = load_data()
        return compute_merchant_profile(df)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/alerts")
def analytics_alerts():
    """
    Full structured alerts payload — used by n8n as the first step
    in its automation workflow. Returns signals, summary, profile, and inventory
    in a single response so n8n can pass it downstream without extra calls.
    """
    try:
        df = load_data()
        return get_alerts_data(df)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# SCHEDULER ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@app.post("/scheduler/run")
def scheduler_run():
    """
    Run the full daily check pipeline:
      analytics → decision engine → Cognee context → AI reasoning → save notification
    Called by: n8n workflow (HTTP Request node) and frontend "Run New Check" button.
    """
    try:
        return run_daily_check()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scheduler/history")
def scheduler_history():
    try:
        return {"history": load_notifications()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# COGNEE MEMORY ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@app.post("/cognee/add-memory")
async def cognee_add_memory(req: MemoryRequest):
    """
    Store a new merchant memory in Cognee.
    The merchant can use this via the Memory tab in the frontend to provide context.
    Example: "Monday sales are always low because the market is closed."
    """
    try:
        result = await add_merchant_memory(
            text=req.text,
            memory_type=req.memory_type,
            merchant_id=req.merchant_id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/cognee/search")
async def cognee_search(q: str = Query(..., description="Search query for merchant memory")):
    """
    Search Cognee for memories relevant to the given query.
    Used by n8n and the frontend Memory tab.
    """
    try:
        results = await search_merchant_memory(q)
        return {"query": q, "results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cognee/seed")
async def cognee_seed():
    """
    Seed the Cognee knowledge graph with demo merchant memories.
    Call this once during setup to populate memories for the three demo scenarios.
    """
    try:
        result = await seed_demo_memories()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/cognee/status")
def cognee_status():
    """Check if Cognee is available and configured."""
    return get_cognee_status()


# ═══════════════════════════════════════════════════════════════════
# ALERT RECEIVE ENDPOINT (called by n8n after workflow completes)
# ═══════════════════════════════════════════════════════════════════

@app.post("/alerts/receive")
def alerts_receive(req: AlertReceiveRequest):
    """
    Receive a completed alert notification from n8n.
    n8n calls this endpoint at the end of its workflow (YES branch).
    The notification is saved and appears in the History tab.
    """
    try:
        from datetime import datetime
        notification = {
            "id":               f"n8n_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "timestamp":        datetime.now().isoformat(),
            "source":           req.source,
            "workflow_id":      req.workflow_id,
            "signals_count":    len(req.signals),
            "has_alert":        req.has_alert,
            "priority":         req.priority,
            "recommendation":   req.recommendation,
            "explanation":      req.explanation,
            "what_happened":    req.what_happened,
            "why_it_matters":   req.why_it_matters,
            "evidence":         req.evidence,
            "what_next":        req.what_next,
            "historical_context": req.historical_context,
            "cognee_context_used": bool(req.historical_context),
            "signals":          req.signals,
            "n8n_triggered":    True,
        }
        save_notification(notification)
        logger.info(f"📥 Alert received from n8n — priority: {req.priority}")
        return {"status": "saved", "notification_id": notification["id"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# CHAT ENDPOINT
# ═══════════════════════════════════════════════════════════════════

@app.post("/chat")
def chat(req: ChatRequest):
    try:
        answer = answer_question(req.message)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
