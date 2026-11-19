"""Service endpoints: health check and frontend configuration."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from demo_data import DEMO_ACCOUNTS
from enums import ClientStatus, DealStage

router = APIRouter(prefix="/api", tags=["Meta"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    """Used by Docker / the hosting platform to check that the app and DB are up."""
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.get("/config")
def frontend_config():
    """
    Everything the frontend needs before login.

    The stage and status lists come from the enums, so the UI never has its
    own hard-coded copy that could drift from the backend.
    """
    settings = get_settings()
    return {
        "demo_mode": settings.demo_mode,
        "demo_accounts": DEMO_ACCOUNTS if settings.demo_mode else [],
        "deal_stages": [stage.value for stage in DealStage],
        "closed_stages": [stage.value for stage in DealStage if stage.is_closed],
        "client_statuses": [status.value for status in ClientStatus],
    }
