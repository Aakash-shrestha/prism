# PRism

An AI-powered GitHub bot that reviews pull requests automatically — catching bugs, security issues, and missing error handling before a human reviewer ever looks at the diff.

> **Demo GIF** — replace this line with a screen recording of a PR receiving comments

---

## What it does

When you open or push to a pull request, PRism receives a webhook from GitHub and queues a review in the background. Within seconds, it posts inline comments directly on the diff — pointing to the exact file and line where an issue was found. Comments are classified by severity: **critical** issues that must be fixed before merge, **suggestions** worth addressing, and **nitpicks** that are optional. PRism won't flood your PR with noise — a critic pass filters out vague or hallucinated comments before anything gets posted.

---

## Architecture

```
GitHub PR opened / pushed
        │
        ▼
POST /webhook/github  (FastAPI — HMAC signature verified)
        │
        ▼
   Redis queue
        │
        ▼
 Celery worker
        │
        ├──── PostgreSQL  (dedup check + persist review & comments)
        │
        ▼
LangGraph agent
   ┌────────────────────────────────────────┐
   │  classify  →  generate  →  critic     │
   └────────────────────────────────────────┘
        │
        ▼
GitHub PR inline comments
```

The agent runs three nodes in sequence: **classify** determines the type of change (feature, bug fix, refactor, etc.), **generate** produces review comments with a focus prompt tailored to that type, and **critic** filters the output before anything is posted.

---

## Tech stack

| Layer | Technology |
|---|---|
| API server | Python, FastAPI |
| Task queue | Celery, Redis |
| AI pipeline | LangGraph, Groq (llama-3.3-70b-versatile) |
| Database | PostgreSQL, SQLAlchemy (async), Alembic |
| HTTP client | httpx |
| Package manager | uv |

---

## Local setup

**1. Clone and install dependencies**
```bash
git clone https://github.com/your-username/prism.git
cd prism
uv sync
```

**2. Configure environment**
```bash
cp .env.example .env
```

Edit `.env`:
```
GITHUB_WEBHOOK_SECRET=your_webhook_secret
GITHUB_TOKEN=ghp_your_token
GROQ_API_KEY=gsk_your_key
REDIS_URL=redis://localhost:6379
DATABASE_URL=postgresql+asyncpg://localhost/prism
```

**3. Start Redis**
```bash
redis-server
```

**4. Create the database and run migrations**
```bash
createdb prism
uv run alembic upgrade head
```

**5. Start the API server**
```bash
uv run uvicorn src.prism.main:app --reload
```

**6. Start the Celery worker** (separate terminal)
```bash
uv run celery -A prism.worker.celery_app worker --loglevel=info
```

**7. Expose the webhook with ngrok** (for local GitHub testing)
```bash
ngrok http 8000
# Set https://<your-ngrok-url>/webhook/github as the GitHub webhook URL
```

---

## Eval results

The agent is tested against 8 hand-crafted cases covering SQL injection, race conditions, mutable default arguments, missing authentication, silent `None` returns, and false-positive resistance.

| Case | Expected diff type | Score |
|---|---|---|
| `off_by_one` | feature | 60 |
| `sql_injection_fstring` | feature | 100 |
| `race_condition_lazy_cache` | feature | 80 |
| `mutable_default_argument` | feature | 70 |
| `missing_auth_admin_endpoint` | feature | 100 |
| `silent_none_return_on_exception` | refactor | 80 |
| `style_only` | style | 100 |
| `clean_addition` | feature | 100 |
| **Average** | | **86 / 100** |

> Run `uv run python -m evals.run_evals` to populate this table. Results are written to `evals/results.jsonl`.

---

## Project structure

```
src/prism/
├── main.py           # FastAPI app entry point
├── webhook.py        # GitHub webhook handler — verifies HMAC signature, dispatches task
├── worker.py         # Celery task — orchestrates fetch → review → persist → post
├── agent.py          # LangGraph pipeline: classify → generate → critic
├── github_client.py  # GitHub API calls with exponential backoff retry
├── repository.py     # SQLAlchemy queries — reviews and comments
├── models.py         # ORM models: Review, Comment
├── schemas.py        # Pydantic models shared across layers
├── config.py         # Typed settings loaded from .env
└── logging.py        # JSON structured logging

evals/
├── cases.py          # EvalCase definitions + EvalResult model
├── judge.py          # LLM-as-judge: scores agent output against expected issues
└── run_evals.py      # Eval runner — prints scored results, writes evals/results.jsonl

migrations/
└── versions/         # Alembic migration files
```
