# Flash-Sale Inventory System — Progress Tracker

## 1. Project Goal
Build a high-concurrency flash-sale backend that handles thousands of simultaneous purchase requests without overselling.

**Target stack:** FastAPI, PostgreSQL, Redis, AWS SQS, Docker, Kubernetes, AWS, Locust, Prometheus/Grafana.

**Learning style:** Project-first, concise explanations, step-by-step implementation. Avoid reteaching FastAPI basics or unnecessary theory.

## 2. Development Environment
- OS: Windows
- Editor: VS Code
- Project folder: `C:\Users\Samrudh0045\Studies\Development Learning\FastAPI\Flash-Sale-System`
- Python virtual environment: `.venv`
- GitHub repository: https://github.com/Samrudh7-0045/Flash-Sale-System
- PostgreSQL database: `flash_sale`

## 3. Current Project Structure
```text
Flash-Sale-System/
├── .venv/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   └── schemas.py
├── tests/
├── .env
├── .gitignore
├── README.md
└── requirements.txt
```

## 4. Completed Work

### Environment and tools
- Set up Python virtual environment.
- Installed FastAPI and Uvicorn.
- Installed SQLAlchemy, psycopg and python-dotenv.
- Configured Git and GitHub.
- Created `.gitignore` to exclude `.venv/`, Python cache files and `.env`.

### PostgreSQL
- Installed PostgreSQL 18 and pgAdmin 4.
- Created the `flash_sale` database.
- Created the `products` table.
- Added two products:
  - Gaming Mouse — ₹2,499 — stock 100
  - Mechanical Keyboard — ₹5,999 — stock 50

### Database integration
- Created `.env` containing `DATABASE_URL`. Never commit this file or expose its password.
- Connected SQLAlchemy to PostgreSQL using psycopg.
- Created the SQLAlchemy `Product` model in `app/models.py`.
- Created `SessionLocal` and the `get_db()` session dependency in `app/database.py`.
- Created the `ProductResponse` Pydantic schema in `app/schemas.py`.

### API
- Created the FastAPI application in `app/main.py`.
- `GET /` returns a running-status message.
- Implemented `GET /products` to retrieve products from PostgreSQL.
- Added the `stock` field to the database, model and response schema.
- Verified the database connection and product retrieval.

## 5. Architecture Understood So Far

```text
Browser / Postman
       ↓ HTTP
     Uvicorn
       ↓
     FastAPI
       ↓
 SQLAlchemy Session
       ↓
 SQLAlchemy Engine
       ↓
     psycopg
       ↓
   PostgreSQL
       ↓
   products table
       ↓
    JSON response
```

Responsibilities:
- Uvicorn: runs the application and handles HTTP connections.
- FastAPI: handles API routes and application logic.
- SQLAlchemy: provides database operations and ORM mapping.
- psycopg: communicates with PostgreSQL.
- PostgreSQL: stores persistent data.
- `.env`: holds configuration and database credentials.
- `.gitignore`: prevents specified files from being tracked by Git.

## 6. Git Progress
Latest commit:
`d17832e — Add product inventory API`

Successfully pushed to GitHub on branch `main`.

**Pending verification:** `requirements.txt` appeared as modified before the latest commit and was not included in that commit. Run `git status` and inspect the change before deciding whether to commit it.

## 7. Current Learning Stage
**Stage 1: Basic backend + PostgreSQL integration**

Completed: environment setup, database connection, product model and read-only product API.

Not implemented yet:
- Create/update products through API
- Order creation and inventory deduction
- Transactions and concurrency protection
- Redis caching, atomic inventory operations and rate limiting
- Temporary reservations
- SQS and background workers
- Retry handling and idempotency
- Docker, Kubernetes and AWS deployment
- Load testing and monitoring

## 8. Next Step
Continue from the existing code. First verify Git status and ensure `requirements.txt` is correct.

Then build the next small, necessary backend feature, testing it before proceeding toward order creation and safe inventory deduction.

Do not introduce Redis, SQS, Docker, Kubernetes or AWS prematurely.

## 9. Working Rules
- Work on one logical block at a time.
- Give related commands together where practical.
- Explain what each new component does and how it connects to existing components.
- Avoid lengthy theory and basic FastAPI reteaching.
- Test each feature before moving forward.
- Commit and push at meaningful milestones.
- Update this progress tracker at the end of each working session.

## 10. Daily Learning Log

### Day 1 — October 7, 2026
- Set up the project environment and PostgreSQL integration.
- Built the initial FastAPI application and product inventory API.

### Day 2 — October 9, 2026
- Implemented Redis-backed temporary reservations and PostgreSQL inventory deduction.
- Added idempotency keys and concurrent order/reservation tests.
- Verified that 10 simultaneous requests with the same idempotency key created only one order and deducted stock once.
- Git commit: `1bda992` — `Add concurrent order and idempotency tests`
- Pushed changes to GitHub; working tree clean.
- **Next:** Transaction safety, rollback and failure handling.

### Day 3 — October 10, 2026
- Implemented Redis caching for `GET /products` with a 30-second TTL.
- Added cache read, write, and invalidation helpers in `app/product_cache.py`.
- Integrated cache invalidation after successful order commits.
- Added cache-helper and API integration tests.
- Verified Python syntax, `test_product_cache.py` (**1 passed**), and `git diff --check`.
- API and full-suite tests remain blocked during collection because Windows Application Control blocks the Python `_ctypes` DLL in the current environments. No conclusion about API test correctness can be drawn yet.
- Identified a potential race between cache population and invalidation; this remains unresolved.
- Cache changes are **uncommitted**.
- **Next:** Resolve the test-environment restriction and verify API behavior, then address cache invalidation races before committing.