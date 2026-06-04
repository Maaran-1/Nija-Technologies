# Workforce Optimization Platform (WOP)

AI-powered workforce optimization system that integrates with **Zoho Projects** to provide real-time utilization analytics, project health monitoring, and automated task redistribution recommendations.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                        Nginx (Port 80)                        │
│              API Proxy /api  ←→  SPA /                       │
└──────────────┬───────────────────────────┬───────────────────┘
               │                           │
     ┌─────────▼──────────┐     ┌──────────▼─────────┐
     │  FastAPI Backend    │     │   React Frontend    │
     │  (Port 8000)        │     │   (Port 3000/80)    │
     └─────────┬──────────┘     └────────────────────┘
               │
     ┌─────────▼──────────┐     ┌────────────────────┐
     │   PostgreSQL 16     │     │   Redis 7           │
     │   (Port 5432)       │     │   (Port 6379)       │
     └────────────────────┘     └──────────┬─────────┘
                                           │
                               ┌───────────▼────────┐
                               │  Celery Worker+Beat │
                               └────────────────────┘
```

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Zoho Projects account with API access

### 1. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your values:
- `JWT_SECRET_KEY` — generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- `ENCRYPTION_KEY` — generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_PORTAL_ID`

### 2. Start All Services

```bash
docker compose up -d
```

### 3. Run Database Migrations

```bash
docker compose exec api alembic upgrade head
```

### 4. Create Admin User

```bash
docker compose exec api python -c "
from app.database import SessionLocal
from app.models.user import PlatformUser
from app.core.auth import hash_password
import uuid

db = SessionLocal()
admin = PlatformUser(
    id=uuid.uuid4(),
    name='Admin',
    email='admin@company.com',
    hashed_password=hash_password('changeme123'),
    role='admin',
    is_active=True,
)
db.add(admin)
db.commit()
print('Admin created')
"
```

### 5. Connect Zoho OAuth

```bash
# Get authorization URL
curl http://localhost/api/v1/sync/zoho/auth-url \
  -H "Authorization: Bearer <your_jwt_token>"
```

Visit the URL, authorize, and the callback will save tokens.

### 6. Trigger Initial Sync

```bash
curl -X POST http://localhost/api/v1/sync/full \
  -H "Authorization: Bearer <your_jwt_token>"
```

---

## API Documentation

When `DEBUG=true`, Swagger UI is available at: `http://localhost:8000/api/docs`

### Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/login` | Get JWT tokens |
| GET | `/api/v1/analytics/dashboard` | Executive dashboard |
| GET | `/api/v1/utilization/team` | Team utilization overview |
| GET | `/api/v1/recommendations` | List recommendations |
| POST | `/api/v1/recommendations/{id}/approve` | Approve recommendation |
| GET | `/api/v1/analytics/portfolio-health` | Project health scores |
| POST | `/api/v1/sync/full` | Trigger full Zoho sync |
| GET | `/api/v1/health` | Service health check |

---

## Development Setup

### Backend

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment
cp .env.example .env
# Edit .env — set DATABASE_URL, REDIS_URL, etc.

# Run migrations
alembic upgrade head

# Start dev server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev  # Starts at http://localhost:3000
```

### Workers (separate terminal)

```bash
# Celery worker
celery -A app.workers.celery_app worker --loglevel=info

# Celery beat (in another terminal)
celery -A app.workers.celery_app beat --loglevel=info
```

---

## Project Structure

```
wop/
├── app/
│   ├── main.py                 # FastAPI application factory
│   ├── config.py               # Settings (pydantic-settings)
│   ├── database.py             # SQLAlchemy engine/session
│   ├── core/
│   │   ├── auth.py             # JWT authentication
│   │   ├── exceptions.py       # Custom exception hierarchy
│   │   ├── responses.py        # Standard API response helpers
│   │   └── logging_config.py   # Structured logging (structlog)
│   ├── models/                 # SQLAlchemy ORM models
│   ├── schemas/                # Pydantic request/response schemas
│   ├── routers/                # FastAPI routers (one per domain)
│   ├── integrations/zoho/      # Zoho OAuth + API client + normalizer
│   ├── analytics/              # Utilization, project scoring, team health
│   ├── recommendations/        # Recommendation engine pipeline
│   └── workers/                # Celery tasks and beat schedule
├── alembic/                    # Database migrations
│   └── versions/               # Migration scripts
├── frontend/                   # React TypeScript SPA
│   ├── src/
│   │   ├── api/                # Axios client + service layer
│   │   ├── store/              # Zustand state stores
│   │   ├── types/              # TypeScript interfaces
│   │   ├── pages/              # Page components
│   │   └── components/         # Shared components
│   └── Dockerfile
├── nginx/nginx.conf            # Reverse proxy config
├── Dockerfile                  # Backend Docker image
├── docker-compose.yml          # Full stack orchestration
└── .env.example                # Environment template
```

---

## Recommendation Engine

The recommendation engine runs in four stages:

1. **Candidate Selection** — Finds overloaded users (>85% utilization)
2. **Task Eligibility** — Filters tasks that can be reassigned (not due soon, has estimated hours)
3. **Recipient Scoring** — Scores available users on: capacity (35%), skill match (25%), project familiarity (20%), completion rate (10%), WIP depth (10%)
4. **Impact Simulation** — Computes projected utilization deltas and confidence scores

Recommendations require manager approval before any task reassignment occurs.

---

## Sync Schedule

| Sync Type | Interval | Description |
|-----------|----------|-------------|
| Full Sync | Hourly | All entities from Zoho |
| Incremental Sync | 15 min | Tasks + timesheets (delta) |
| Analytics Recompute | Daily 02:00 | Utilization snapshots |
| Project Health Scoring | Every 4h | Health score computation |
| Recommendation Generation | Every 15 min | After incremental sync |

---

## Tech Stack

**Backend:** FastAPI, SQLAlchemy 2, PostgreSQL 16, Redis, Celery, Alembic, structlog  
**Frontend:** React 18, TypeScript, Tailwind CSS, React Query, Zustand, Recharts  
**Infrastructure:** Docker Compose, Nginx, Celery Beat  
**Integration:** Zoho Projects REST API v3 (OAuth 2.0)
