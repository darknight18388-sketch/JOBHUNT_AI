# JOBHUNT AI
Free, open-source, approval-based AI job search assistant (React + FastAPI + PostgreSQL + Ollama).

## Quick start (Kali / Debian)
```bash
git clone https://github.com/darknight18388-sketch/JOBHUNT_AI.git
cd JOBHUNT_AI
./scripts/setup_kali.sh     # installs packages, creates the database and backend/.env, runs tests
./scripts/dev.sh            # backend :8000 + frontend :5173 (Ctrl+C stops both)
```
Open http://localhost:5173 and register. `backend/.env` is created for you (never commit it).
Optional free job-source keys (Jooble, Careerjet, Adzuna) go in `backend/.env`; see `.env.example`.

## Company career pages
Under Find Jobs -> Company career pages, add a company's careers link (Greenhouse, Lever, Ashby, Recruitee, Workable, or any page with standard job data). See `docs/JOB_SOURCES.md`.

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
