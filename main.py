import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from config import get_settings
from routers import analytics, auth, clients, deals, meta, tasks, users

settings = get_settings()
logger = logging.getLogger("uvicorn.error")  # shows up in the server log

STATIC_DIR = Path(__file__).parent / "static"

if settings.secret_key == "CHANGE_ME":
    logger.warning("SECRET_KEY is not set - tokens can be forged. Set it in .env before deploying.")

def _reset_demo_data() -> None:
    import demo_data
    from database import SessionLocal

    session = SessionLocal()
    try:
        demo_data.reset(session)
        demo_data.seed(session)
        logger.info("Demo data has been reset")
    finally:
        session.close()


async def _demo_reset_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(_reset_demo_data)
        except Exception:  # keep the loop alive; the next run may succeed
            logger.exception("Demo reset failed")
        await asyncio.sleep(settings.demo_reset_hours * 3600)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(_demo_reset_loop()) if settings.demo_mode else None
    yield
    if task:
        task.cancel()


app = FastAPI(
    lifespan=lifespan,
    title="CRM API",
    description="Clients, deals pipeline, tasks and analytics with role-based access.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    # frame-ancestors decides who may embed the app in an <iframe>
    # (the portfolio site in demo mode, nobody else by default).
    response.headers["Content-Security-Policy"] = f"frame-ancestors {settings.frame_ancestors}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# The schema is created by Alembic only (`alembic upgrade head`), never by
# Base.metadata.create_all(): that would bypass the migrations.

# Adding a new entity:
#   1. model -> models.py
#   2. schemas -> schemas.py
#   3. database functions -> crud.py
#   4. routes -> routers/<new_file>.py
#   5. register the router below
app.include_router(meta.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(clients.router)
app.include_router(deals.router)
app.include_router(tasks.router)
app.include_router(analytics.router)

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def frontend():
    index = STATIC_DIR / "index.html"
    if not index.exists():
        # The API keeps working even if the frontend files are missing.
        return HTMLResponse("<h1>CRM API is running</h1><p>Documentation: <a href='/docs'>/docs</a></p>")
    return FileResponse(index)


@app.get("/dashboard", include_in_schema=False)
def old_dashboard_url():
    """The dashboard used to be a separate page; keep old links working."""
    return RedirectResponse("/#/dashboard")
