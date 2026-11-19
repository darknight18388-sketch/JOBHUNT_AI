# JOBHUNT AI
Free, open-source, approval-based AI job search assistant (React + FastAPI + PostgreSQL + Ollama).

## Run backend
```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
uvicorn app.main:app --reload --port 8000
pytest
```
## Run frontend
```bash
cd frontend
npm install
npm run dev     # http://localhost:5173
```
## Roadmap
- [x] Phase 1 - Environment check script
- [x] Phase 2 - Project skeleton and UI
- [x] Phase 3 - Database and authentication
- [x] Phase 4 - CV upload and parsing
- [x] Phase 5 - Job connectors (+ country search)
- [ ] Phase 6 - Matching engine
- [ ] Phase 7 - AI documents
- [ ] Phase 8 - Application workflow (explicit approval only)
- [ ] Phase 9 - Tracking and notifications
- [ ] Phase 10 - Admin, security, QA
- [ ] Phase 11 - Deployment

Safety rules: never invent candidate facts, never bypass site restrictions, never submit without explicit user approval.
