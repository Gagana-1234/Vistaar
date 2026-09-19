# Vistaar ⚡ — Proactive AI Business Advisor for Merchants

> **Hackathon project.** All data is synthetic. No real customer PII is used.

Vistaar doesn't just tell merchants *what happened* — it tells them *what deserves their attention next*.

**OBSERVE → ANALYZE → REMEMBER → REASON → DECIDE → ACT**

---

## Architecture

```
┌───────────────────┐
│  Merchant Dataset │  (synthetic order-level CSV + inventory.json)
└─────────┬─────────┘
          ↓
   ┌─────────────┐
   │     n8n     │  Automation / Scheduler (daily 9 AM trigger)
   └──────┬──────┘
          ↓
┌───────────────────┐
│ Backend Analytics │  FastAPI — deterministic metrics (no LLM guessing)
└─────────┬─────────┘
          ↓
┌───────────────────┐
│  Decision Engine  │  Configurable threshold rules → priority level
└─────────┬─────────┘
          ↓
┌───────────────────┐
│  Cognee Memory    │  Persistent merchant knowledge graph
└─────────┬─────────┘
          ↓
┌───────────────────┐
│   Gemini AI       │  Reasoning with analytics + memory context
└─────────┬─────────┘
          ↓
┌───────────────────┐
│ Alert / Dashboard │  React frontend — explainable alerts
└───────────────────┘
```

---

## What Each Component Does

| Component | Role |
|-----------|------|
| **Backend (FastAPI)** | Calculates all metrics deterministically. The AI never invents numbers. |
| **Decision Engine** | Configurable threshold rules evaluate signals before calling the AI. |
| **Cognee** | Persistent merchant memory (context, events, preferences, historical alerts). |
| **Gemini AI** | Reasons using pre-calculated metrics + Cognee context. Returns full explainability. |
| **n8n** | Orchestrates the full pipeline automatically every morning at 9 AM. |
| **Frontend** | React dashboard showing alerts, inventory, memory interface, and chat. |

---

## Vistaar — n8n + Cognee Setup

### Required Environment Variables

Create `backend/.env` based on `backend/.env.example`:

```bash
# ── REQUIRED (Gemini AI for reasoning and chat)
GEMINI_API_KEY=your_gemini_api_key_here

# ── OPTIONAL (Cognee memory — system works without this)
COGNEE_LLM_PROVIDER=openai
COGNEE_LLM_API_KEY=your_openai_api_key_here
COGNEE_LLM_MODEL=gpt-4o-mini
COGNEE_EMBEDDING_PROVIDER=openai
COGNEE_EMBEDDING_API_KEY=your_openai_api_key_here

# ── OPTIONAL (n8n webhook for demo notifications)
N8N_WEBHOOK_URL=

# ── OPTIONAL (decision engine threshold tuning)
ALERT_PRIORITY_SPIKE_HIGH=30
ALERT_PRIORITY_SPIKE_MEDIUM=20
ALERT_PRIORITY_DROP_HIGH=30
ALERT_PRIORITY_DROP_MEDIUM=20
ALERT_COVERAGE_DAYS_HIGH=3
ALERT_COVERAGE_DAYS_MEDIUM=7
```

**Get API keys:**
- Gemini (free): https://aistudio.google.com/app/apikey
- OpenAI (paid): https://platform.openai.com/api-keys

---

### Step 1 — Backend Setup

```bash
cd backend

# Activate virtual environment (already created)
venv\Scripts\activate       # Windows
# source venv/bin/activate  # macOS/Linux

# Install dependencies (including cognee)
pip install -r requirements.txt

# Generate synthetic demo data (creates transactions.csv + inventory.json)
python generate_data.py

# Start the backend
uvicorn main:app --port 8000 --reload
```

Backend runs at: **http://localhost:8000**
API docs at: **http://localhost:8000/docs**

---

### Step 2 — Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at: **http://localhost:5173**

---

### Step 3 — Configure n8n (Automation Layer)

#### Install n8n
```bash
# Option A: Docker
docker run -it --rm --name n8n -p 5678:5678 -v ~/.n8n:/home/node/.n8n docker.n8n.io/n8nio/n8n

# Option B: npx (no install)
npx n8n
```

n8n runs at: **http://localhost:5678**

#### Import the Workflow
1. Open http://localhost:5678
2. Click **"Add workflow"** → **"Import from file"**
3. Select `n8n/vistaar_workflow.json`
4. Click **Save**
5. Click **"Test Workflow"** to run it manually

See `n8n/README_N8N.md` for detailed n8n configuration and troubleshooting.

---

### Step 4 — Configure Cognee Memory

Cognee activates automatically when `COGNEE_LLM_API_KEY` is set in `backend/.env`.

#### Seed demo memories (for hackathon demo):
```bash
curl -X POST http://localhost:8000/cognee/seed
```

Or click **"Seed Demo Memories"** in the frontend **Memory** tab.

#### Check Cognee status:
```bash
curl http://localhost:8000/cognee/status
```

#### Add a memory manually:
```bash
curl -X POST http://localhost:8000/cognee/add-memory \
  -H "Content-Type: application/json" \
  -d '{"text": "Monday sales are lower because the market is closed", "memory_type": "MERCHANT_CONTEXT"}'
```

---

### Step 5 — Test the Complete System

```bash
# 1. Verify backend is healthy
curl http://localhost:8000/

# 2. Check signals detected in data
curl http://localhost:8000/analytics/signals

# 3. Get full alerts payload (what n8n fetches)
curl http://localhost:8000/analytics/alerts

# 4. Run full AI reasoning pipeline
curl -X POST http://localhost:8000/scheduler/run

# 5. View saved notifications (what the frontend History tab shows)
curl http://localhost:8000/scheduler/history

# 6. Search Cognee memory
curl "http://localhost:8000/cognee/search?q=cooking+oil+demand"

# 7. Test chat
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Why are cooking oil sales high?"}'
```

---

## Three Demo Scenarios

The synthetic data (`generate_data.py`) embeds three explicit scenarios:

### Scenario 1 — NORMAL (Rice)
- Rice sales stay within the merchant's historical DOW-adjusted band
- No unusual deviation from baseline
- **Expected result:** Decision engine → `NO_ACTION` | AI → no alert
- **How to demo:** Run `/scheduler/run`, show `priority: NO_ACTION`

### Scenario 2 — SALES ANOMALY (Beverages)
- Beverage demand drops ~35% in the last 14 days
- Exceeds `ALERT_PRIORITY_DROP_HIGH` threshold (30%)
- **Expected result:** Decision engine → `HIGH` | AI → `DEMAND_DROP` alert
- **Cognee context:** "A new competing store opened nearby" explains the drop
- **How to demo:** Show the signal, show Cognee memory, show AI explanation

### Scenario 3 — INVENTORY RISK (Cooking Oil)
- Cooking oil demand spikes ~40% in the last 7 days
- No extra restock was done, so stock is critically low
- **Expected result:** Decision engine → `HIGH` + `LOW_STOCK` | AI → restock alert
- **Cognee context:** "Oil demand spiked last September and caused a 3-day stock-out"
- **How to demo:** Show spike + low stock signals, show Cognee historical alert, show AI recommendation

---

## Complete End-to-End Demo Flow

1. **Open frontend** at http://localhost:5173
2. **Dashboard tab** → Show 30-day revenue chart + low-stock banner for cooking oil
3. **Alerts tab** → Show DEMAND_SPIKE and LOW_STOCK signals with metrics
4. **Open n8n** at http://localhost:5678
5. **Click "Test Workflow"** → Watch each node execute in real time
   - Node 2: Backend returns cooking_oil spike signal
   - Node 3: Cognee returns historical stock-out memory
   - Node 4: AI returns HIGH priority with full reasoning
   - Node 5: Routes to YES branch
   - Node 6: Posts alert to backend
6. **Back to frontend** → History tab → New alert appears (sourced from n8n)
7. **Insights tab** → Show full explainability (What happened / Why / Evidence / What next / Historical context)
8. **Memory tab** → Show Cognee memories, add one live: "Diwali season starts next month"
9. **Chat tab** → Ask: *"Why did you alert me about cooking oil?"*
   - AI response uses both analytics data AND Cognee memory context
10. **Chat tab** → Ask: *"Which products should I restock this week?"*

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/analytics/summary` | 7d / 30d category summary |
| GET | `/analytics/signals` | Detected demand/stock signals |
| GET | `/analytics/chart` | Daily revenue (30 days) |
| GET | `/analytics/alerts` | Full alerts payload for n8n |
| GET | `/analytics/inventory` | Inventory snapshot |
| GET | `/analytics/merchant-profile` | DOW baselines + normal ranges |
| POST | `/scheduler/run` | Run full analysis pipeline |
| GET | `/scheduler/history` | Past notifications |
| POST | `/cognee/add-memory` | Store merchant memory |
| GET | `/cognee/search?q=` | Search Cognee memory |
| POST | `/cognee/seed` | Seed demo memories |
| GET | `/cognee/status` | Cognee availability status |
| POST | `/alerts/receive` | Receive alert from n8n |
| POST | `/chat` | Conversational Q&A |

---

## File Structure

```
Vistaar/
├── backend/
│   ├── main.py               ← FastAPI entry point (all endpoints)
│   ├── analytics.py          ← Deterministic metrics engine
│   ├── scheduler.py          ← Daily check orchestrator
│   ├── llm_service.py        ← Gemini AI reasoning
│   ├── chat.py               ← Conversational Q&A
│   ├── generate_data.py      ← Synthetic data generator
│   ├── services/
│   │   ├── cognee_service.py ← Cognee memory layer
│   │   └── decision_engine.py← Priority decision rules
│   ├── data/
│   │   ├── transactions.csv  ← Order-level synthetic data
│   │   ├── inventory.json    ← Inventory snapshot
│   │   └── notifications.json← Saved alerts (auto-created)
│   ├── requirements.txt
│   ├── .env                  ← Your secrets (never commit)
│   └── .env.example          ← Template (safe to commit)
├── frontend/
│   └── src/
│       ├── App.jsx           ← Root (6 tabs)
│       ├── api.js            ← Backend API client
│       └── components/
│           ├── SummaryChart.jsx  ← Dashboard + chart
│           ├── AlertsPanel.jsx   ← Signals + inventory [NEW]
│           ├── InsightCard.jsx   ← AI insight with explainability
│           ├── MemoryPanel.jsx   ← Cognee memory UI [NEW]
│           ├── ChatPanel.jsx     ← Conversational chat
│           └── HistoryView.jsx   ← Past checks timeline
└── n8n/
    ├── vistaar_workflow.json ← Importable n8n workflow
    └── README_N8N.md         ← n8n setup guide
```

---

## Failure Handling

| Failure | Behaviour |
|---------|-----------|
| Cognee unavailable | System continues using analytics only. Memory features show "not configured" status. |
| Gemini API fails | Decision engine result is shown directly. Clearly marked as "AI reasoning unavailable". |
| n8n workflow fails | Backend still works. Merchant can use "Run New Check" button in frontend. |
| Data file missing | Backend auto-generates synthetic data on startup. |
| Inventory file missing | System falls back to in-memory stock tracking. |

---

## Known Limitations & TODOs

- Cognee requires an OpenAI-compatible API key (the Gemini key used for the LLM reasoning does not work directly for Cognee embeddings in the current version — a separate OpenAI key is needed for full Cognee functionality)
- Data is synthetic — not connected to any real POS, payment gateway, or inventory system
- `merchant_id` is hardcoded as `MERCHANT_001` — multi-tenant support is not implemented
- n8n runs locally — for production use, deploy to n8n Cloud or a server
- Cognee knowledge graph is stored locally in the default Cognee data directory

---

## Security Notes

- Never commit `backend/.env` to Git (it is in `.gitignore`)
- Never hardcode API keys in source code
- All credentials are loaded via `python-dotenv` from environment variables
- No real customer PII is used anywhere — all `customer_id` values are synthetic IDs like `CUST_0042`
