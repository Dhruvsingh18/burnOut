# Burnout Tracker

Tracks which apps you use and for how long. A local agent polls your active
window every minute, posts to a backend, and a dashboard shows live data.

## Run locally

### 1. Backend
```
cd backend
python -m venv venv
venv\Scripts\Activate.ps1      # Windows
pip install -r requirements.txt
cp .env.example .env
cd ..
python -m uvicorn backend.main:app --reload
```

### 2. Agent
```
cd agent
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
python tracker.py
```

### 3. Frontend
```
cd frontend
npm install
npx vite
```
Open http://localhost:5173

---

## Deploy to production

### Backend → Railway
1. Push this repo to GitHub
2. railway.app → New Project → Deploy from GitHub repo
3. Set root directory to `backend`
4. Railway auto-adds DATABASE_URL (Postgres) — just add it as an env var
5. Copy the Railway public URL

### Frontend → Vercel
1. vercel.com → New Project → same GitHub repo
2. Set root directory to `frontend`
3. Add environment variable:
   - Key: `VITE_API_URL`
   - Value: your Railway URL (e.g. https://burnout-production.railway.app)
4. Deploy

### Agent (always runs locally)
After deploying the backend, update `agent/.env`:
```
BACKEND_URL=https://your-backend.railway.app
```
Restart the agent — it will now send data to your live backend.

