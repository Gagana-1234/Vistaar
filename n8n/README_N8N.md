# Vistaar — n8n Workflow Setup Guide

## What n8n does in Vistaar

n8n is the **automation/orchestration layer**. It acts as the autonomous scheduler that runs Vistaar's analysis pipeline every morning at 9:00 AM — without the merchant having to do anything.

```
[Schedule Trigger: 9 AM daily]
          ↓
[GET /analytics/alerts]      ← Backend calculates all metrics
          ↓
[GET /cognee/search]         ← Retrieve relevant merchant memories
          ↓
[POST /scheduler/run]        ← AI reasoning pipeline runs
          ↓
[IF has_alert?]
   ↙           ↘
  NO            YES
  ↓              ↓
Stop       POST /alerts/receive   ← Save to dashboard
                 ↓
          [Webhook Notification]  ← Optional demo notification
```

**Important:** n8n calls the Vistaar backend over HTTP. No business logic runs inside n8n itself — it is the orchestrator, not the brain.

---

## Installation

### Option A — Docker (Recommended)

```bash
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  docker.n8n.io/n8nio/n8n
```

### Option B — npx (no install required)

```bash
npx n8n
```

n8n will be available at: **http://localhost:5678**

---

## Importing the Vistaar Workflow

1. Open **http://localhost:5678** in your browser
2. Click **"Add workflow"** → **"Import from file"**
3. Select `Vistaar/n8n/vistaar_workflow.json`
4. Click **Save** (top right)

The workflow will appear with 8 nodes already connected.

---

## Node Overview

| Node | Type | Purpose |
|------|------|---------|
| Schedule Trigger (9 AM Daily) | scheduleTrigger | Runs the workflow automatically every day at 09:00 |
| Get Merchant Alerts Data | httpRequest GET | Calls `/analytics/alerts` — fetches signals, summary, inventory |
| Retrieve Cognee Memory | httpRequest GET | Calls `/cognee/search` — gets relevant merchant memories |
| Run AI Reasoning Pipeline | httpRequest POST | Calls `/scheduler/run` — full decision+AI analysis |
| Alert Required? | if | Checks `has_alert === true` to branch the workflow |
| Post Alert to Dashboard | httpRequest POST | Calls `/alerts/receive` — saves alert to History tab |
| Send Webhook Notification (Demo) | httpRequest POST | Sends a demo notification to a webhook URL |
| No Action Needed | set | Terminates cleanly when no alert is needed |

---

## Configuration

### Backend URL
If your backend is not on `localhost:8000`, update the URL in each HTTP Request node:

1. Open each node by clicking it
2. Change `http://localhost:8000` to your backend URL
3. Click **Save**

### Webhook Notification URL (optional demo)
To see a live notification during the demo:
1. Go to https://webhook.site and copy your unique URL
2. In n8n: open the **"Send Webhook Notification (Demo)"** node
3. Replace the URL with your webhook.site URL
4. **OR** set the `N8N_WEBHOOK_URL` environment variable when starting n8n:
   ```bash
   N8N_WEBHOOK_URL=https://webhook.site/your-id npx n8n
   ```

---

## Testing the Workflow Manually

### Method 1 — Test Workflow button
1. Open the workflow in n8n
2. Click **"Test Workflow"** (top right)
3. Watch each node execute in real time — green = success, red = error
4. Click any node to see its input/output data

### Method 2 — Activate for automatic runs
1. Toggle the **Active** switch (top right of workflow editor)
2. The workflow will now run automatically every day at 9:00 AM
3. Check **Executions** tab to see past runs

### Method 3 — Trigger manually via API
```bash
# This is what n8n does automatically — you can also call it directly
curl -X POST http://localhost:8000/scheduler/run
```

---

## Verifying Each Node

### Node 1: Schedule Trigger
- No configuration needed
- Click "Test Workflow" to bypass the schedule and run immediately

### Node 2: Get Merchant Alerts Data
Expected output keys: `merchant_id`, `signals`, `summary`, `merchant_profile`, `inventory`

```bash
# Test independently
curl http://localhost:8000/analytics/alerts
```

### Node 3: Retrieve Cognee Memory
Expected output keys: `query`, `results`, `count`

```bash
# Test independently
curl "http://localhost:8000/cognee/search?q=cooking+oil+demand+pattern"
```

### Node 4: Run AI Reasoning Pipeline
Expected output keys: `has_alert`, `priority`, `recommendation`, `explanation`, `what_happened`, `why_it_matters`, `evidence`, `what_next`, `historical_context`

```bash
# Test independently
curl -X POST http://localhost:8000/scheduler/run
```

### Node 5: Alert Required?
- YES branch fires when `has_alert === true`
- NO branch fires when no alert is needed (normal scenario)

### Node 6: Post Alert to Dashboard
After this runs, refresh the Vistaar frontend → History tab shows the new alert.

```bash
# Verify alert was saved
curl http://localhost:8000/scheduler/history
```

---

## Demo Flow (Step-by-step)

1. Make sure the Vistaar backend is running: `uvicorn main:app --port 8000`
2. Make sure the Vistaar frontend is running: `npm run dev`
3. Open n8n at http://localhost:5678
4. Import the workflow from `n8n/vistaar_workflow.json`
5. Click **"Test Workflow"**
6. Show the audience each node executing:
   - Node 2 returns the cooking_oil demand spike signal
   - Node 3 returns the Cognee memory about last year's stock-out
   - Node 4 returns HIGH priority with full explainability
   - Node 5 routes to YES (alert required)
   - Node 6 posts to dashboard
7. Switch to the frontend → History tab → new alert appears
8. Switch to Insights tab → show full explainability with Cognee context

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Node returns "Connection refused" | Make sure backend is running on port 8000 |
| Cognee node returns empty results | Check `COGNEE_LLM_API_KEY` in backend `.env` |
| AI node returns "LLM unavailable" | Check `GEMINI_API_KEY` in backend `.env` |
| Workflow not triggering at 9 AM | Toggle **Active** switch in the workflow editor |
| CORS error in browser | Already handled — n8n runs server-side, not in browser |

---

## Environment Variables for n8n

When running n8n with Docker or npx, you can pass environment variables:

```bash
N8N_WEBHOOK_URL=https://webhook.site/your-id \
npx n8n
```

These are used by the workflow nodes via `$env.N8N_WEBHOOK_URL`.
