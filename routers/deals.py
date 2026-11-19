from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

import crud
import models
import schemas
from database import get_db
from dependencies import ensure_owner_or_admin, get_current_user, get_deal_or_404, owner_scope
from enums import DealStage

router = APIRouter(prefix="/api/deals", tags=["Deals"])


@router.post("/", response_model=schemas.DealResponse, status_code=status.HTTP_201_CREATED)
def create_deal(
    deal: schemas.DealCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    client = crud.get_client(db, deal.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    ensure_owner_or_admin(current_user, client.owner_id)
    # The deal belongs to the client's manager; for an unassigned client it is
    # assigned to whoever creates the deal.
    owner_id = client.owner_id if client.owner_id is not None else current_user.id
    created = crud.create_deal(db, deal, owner_id=owner_id)
    return crud.get_deal(db, created.id)


@router.get("/", response_model=list[schemas.DealResponse])
def get_all_deals(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    stage: Optional[DealStage] = None,
    client_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.get_deals(
        db,
        skip=skip,
        limit=limit,
        stage=stage.value if stage else None,
        client_id=client_id,
        owner_id=owner_scope(current_user),
    )


@router.get("/{deal_id}", response_model=schemas.DealResponse)
def get_deal(
    deal: models.Deal = Depends(get_deal_or_404),
    current_user: models.User = Depends(get_current_user),
):
    ensure_owner_or_admin(current_user, deal.owner_id)
    return deal


@router.get("/{deal_id}/history", response_model=list[schemas.StageChangeResponse])
def get_deal_history(
    deal: models.Deal = Depends(get_deal_or_404),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Every stage transition of the deal, oldest first."""
    ensure_owner_or_admin(current_user, deal.owner_id)
    return crud.get_stage_history(db, deal.id)


@router.patch("/{deal_id}", response_model=schemas.DealResponse)
def update_deal(
    data: schemas.DealUpdate,
    deal: models.Deal = Depends(get_deal_or_404),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ensure_owner_or_admin(current_user, deal.owner_id)
    return crud.update_deal(db, deal, data, user_id=current_user.id)


@router.delete("/{deal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deal(
    deal: models.Deal = Depends(get_deal_or_404),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ensure_owner_or_admin(current_user, deal.owner_id)
    crud.delete_deal(db, deal)
