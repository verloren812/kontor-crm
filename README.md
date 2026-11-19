# Kontor CRM

A CRM for small businesses: clients, a drag-and-drop deal pipeline, follow-up
tasks and sales analytics, with role-based access for admins and sales managers.

Backend: **FastAPI, SQLAlchemy 2, PostgreSQL, Alembic**. Frontend: plain
**JavaScript** (ES modules, no framework, no build step) talking to the REST API.

![Overview dashboard](docs/dashboard.png)

| Pipeline | Deal details with stage history |
| --- | --- |
| ![Pipeline board](docs/pipeline.png) | ![Deal drawer](docs/deal.png) |

## Features

- **Clients** with search (name, phone, e-mail), status filter and inline editing
- **Pipeline board**: drag a deal to another stage; every move is recorded in the
  deal's stage history
- **Tasks** grouped into overdue / today / next 7 days, with an overdue badge in
  the navigation
- **Dashboard**: open pipeline by stage, won value, win rate, overdue and upcoming
  tasks, revenue per manager (admins)
- **Roles**: managers see their own and unassigned records, admins see everything
  and manage the team
- **Interactive API docs** at `/docs` (Swagger UI)
- **Demo mode** with fictional data that resets itself every few hours

## Engineering decisions

The interesting part of this project is in the details that are easy to get
wrong. Each one is covered by tests.

| Topic | Decision |
| --- | --- |
| Access control | One query helper applies "own or unassigned" to every list. Foreign records return **404, not 403**, so the API does not even confirm they exist. |
| Tokens | The JWT `sub` holds the **user id, not the username**: renaming a user does not log them out, and a reused username cannot inherit an old token. |
| Passwords | bcrypt ignores everything after **72 bytes**, so longer passwords are rejected (bytes, not characters, because of UTF-8). |
| Money | `NUMERIC(12, 2)` and `Decimal` end to end. With `float`, three deals of 0.10 add up to 0.30000000000000004. |
| Time | All timestamps are `timestamptz`. A custom `UTCDateTime` column type makes SQLite behave like PostgreSQL, which otherwise turned "10:00 Berlin" into "10:00 UTC". |
| Phone numbers | Normalized before saving (`+49 151 123-45-67` = `0049 1511234567`), so the UNIQUE constraint really prevents duplicates. A race between two requests returns **409** instead of a 500. |
| Pipeline analytics | Stage transitions are stored in `deal_stage_changes`, so conversion and time-in-stage can be calculated, not just the current state. |
| Database work | Aggregates are computed with `GROUP BY` in the database; lists use eager loading (no N+1 queries). Indexes match the real queries, including a partial index for open tasks. |
| Schema changes | Only through Alembic. Tests build the database from scratch, compare it with the models, run downgrade/upgrade and check the data migrations. |
| Enums | Request schemas accept only known stages/statuses; response schemas accept any string, so old data never breaks a page. The UI reads the lists from `/api/config` instead of keeping its own copy. |

## Quick start

### With Docker (PostgreSQL)

```bash
docker compose up --build
docker compose exec web python demo_data.py      # optional: fictional demo data
```

Open http://localhost:8000 and sign in with one of the demo accounts printed
by the last command.

### Without Docker (SQLite)

```bash
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt

cp .env.example .env                # then set SECRET_KEY
alembic upgrade head
python demo_data.py                 # or: python create_admin.py
uvicorn main:app --reload
```

On Windows, `run.bat` applies the migrations and starts the server.

## Tests

```bash
pytest                                                    # SQLite in memory
TEST_DATABASE_URL=postgresql+psycopg2://user:pass@localhost/crm_test pytest
```

134 tests cover access rules, authentication, validation, money and time
handling, the dashboard figures, migrations and the demo data. GitHub Actions
runs the suite against both SQLite and PostgreSQL 16.

## Project structure

```
main.py             app setup, security headers, demo reset, frontend delivery
config.py           settings from environment / .env
database.py         engine and session
models.py           SQLAlchemy models (User, Client, Deal, DealStageChange, Task)
schemas.py          Pydantic request/response schemas, phone normalization
enums.py            roles, client statuses, deal stages
crud.py             all database queries
dependencies.py     authentication, role checks, record lookup
security.py         password hashing, JWT
routers/            auth, users, clients, deals, tasks, analytics, meta
migrations/         Alembic migrations 0001-0005
static/             frontend: index.html, css/, js/ (views per page)
demo_data.py        fictional demo data, reset and seed
create_admin.py     creates the first admin on a new server
tests/              pytest suite
```

## API overview

| Method | Path | Who |
| --- | --- | --- |
| POST | `/api/auth/login` | everyone |
| POST | `/api/auth/register` | admin |
| GET | `/api/users/me` | signed in |
| GET, PATCH | `/api/users/`, `/api/users/{id}/role` | admin |
| GET, POST, PATCH | `/api/clients/...` | own or unassigned |
| DELETE | `/api/clients/{id}` | admin |
| GET, POST, PATCH, DELETE | `/api/deals/...` | own or unassigned |
| GET | `/api/deals/{id}/history` | own or unassigned |
| GET, POST, PATCH, DELETE | `/api/tasks/...` | own or unassigned |
| GET | `/api/analytics/dashboard` | signed in (scoped by role) |
| GET | `/api/health`, `/api/config` | everyone |

Full schemas: `/docs` on a running instance.

## Configuration

All settings are environment variables (see `.env.example`):
`SECRET_KEY`, `DATABASE_URL`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `CORS_ORIGINS`,
`DEMO_MODE`, `DEMO_RESET_HOURS`, `FRAME_ANCESTORS`.

`DEMO_MODE=true` shows the demo logins on the sign-in page and **wipes and
re-seeds the database** on startup and every `DEMO_RESET_HOURS`. Never enable
it on a database with real data.

## License

MIT, see [LICENSE](LICENSE).
