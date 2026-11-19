from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import crud
import models
import schemas
from database import get_db
from dependencies import get_current_user, owner_scope

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/dashboard", response_model=schemas.DashboardResponse)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Admins see the whole company, managers only what they can access."""
    return crud.get_dashboard_data(db, owner_id=owner_scope(current_user))
