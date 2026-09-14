from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
import uvicorn
from pathlib import Path

from analytics import load_data, compute_summary, detect_signals, get_chart_data
from scheduler import run_daily_check, load_notifications
from chat import answer_question

# Ensure data directory exists and data is generated if missing
data_dir = Path(__file__).parent / 'data'
data_dir.mkdir(parents=True, exist_ok=True)
if not (data_dir / 'transactions.csv').exists():
    from generate_data import generate_data
    generate_data()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-run daily check if no notifications exist
    notifications = load_notifications()
    if not notifications:
        run_daily_check()
    yield

app = FastAPI(title="Vistaar API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

@app.get("/")
def read_root():
    return {"message": "Vistaar API", "status": "ok"}

@app.get("/analytics/summary")
def get_summary():
    try:
        df = load_data()
        return compute_summary(df)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics/signals")
def get_signals():
    try:
        df = load_data()
        return {"signals": detect_signals(df)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics/chart")
def get_chart():
    try:
        df = load_data()
        return get_chart_data(df)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/scheduler/run")
def scheduler_run():
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

@app.post("/chat")
def chat(req: ChatRequest):
    try:
        answer = answer_question(req.message)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
