# Vistaar - AI Business Advisor

A proactive AI advisor for kirana merchants.

## Run Instructions

### 1. Get a free Gemini API key
https://aistudio.google.com/app/apikey

### 2. Set your API key
Edit backend/.env:
  GEMINI_API_KEY=your_key_here

### 3. Start the Backend
  cd backend
  venv\Scripts\pip install -r requirements.txt
  venv\Scripts\python generate_data.py
  venv\Scripts\uvicorn main:app --port 8000 --reload

API at http://localhost:8000

### 4. Start the Frontend (new terminal)
  cd frontend
  npm install
  npm run dev

App at http://localhost:5173

## Demo
1. Open http://localhost:5173
2. Dashboard tab: see 30-day revenue chart
3. Insights tab: AI flags cooking oil demand spike + restock recommendation
4. Chat: ask 'Why are you telling me this?' for grounded explanation
5. History: view past daily checks

