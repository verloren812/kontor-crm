from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

import crud
import models
import schemas
from database import get_db
from dependencies import (
    ensure_owner_or_admin,
    get_client_or_404,
    get_current_user,
    owner_scope,
    require_role,
)
from enums import ClientStatus, Role

router = APIRouter(prefix="/api/clients", tags=["Clients"])

DUPLICATE_PHONE = "A client with this phone number already exists"


@router.post("/", response_model=schemas.ClientResponse, status_code=status.HTTP_201_CREATED)
def create_client(
    client: schemas.ClientCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Friendly early check; the UNIQUE constraint still catches race conditions.
    if crud.get_client_by_phone(db, client.phone):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=DUPLICATE_PHONE)
    try:
        return crud.create_client(db, client, owner_id=current_user.id)
    except crud.DuplicatePhoneError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=DUPLICATE_PHONE)


@router.get("/", response_model=list[schemas.ClientResponse])
def get_all_clients(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status_filter: Optional[ClientStatus] = Query(None, alias="status"),
    search: Optional[str] = Query(None, max_length=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.get_clients(
        db,
        skip=skip,
        limit=limit,
        status=status_filter.value if status_filter else None,
        search=search,
        owner_id=owner_scope(current_user),
    )


@router.get("/{client_id}", response_model=schemas.ClientResponse)
def get_client(
    client: models.Client = Depends(get_client_or_404),
    current_user: models.User = Depends(get_current_user),
):
    ensure_owner_or_admin(current_user, client.owner_id)
    return client


@router.patch("/{client_id}", response_model=schemas.ClientResponse)
def update_client(
    data: schemas.ClientUpdate,
    client: models.Client = Depends(get_client_or_404),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ensure_owner_or_admin(current_user, client.owner_id)
    if data.phone is not None:
        existing = crud.get_client_by_phone(db, data.phone)
        if existing and existing.id != client.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=DUPLICATE_PHONE)
    try:
        return crud.update_client(db, client, data)
    except crud.DuplicatePhoneError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=DUPLICATE_PHONE)


@router.patch("/{client_id}/status", response_model=schemas.ClientResponse)
def update_client_status(
    status_data: schemas.ClientUpdateStatus,
    client: models.Client = Depends(get_client_or_404),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ensure_owner_or_admin(current_user, client.owner_id)
    return crud.update_client(db, client, schemas.ClientUpdate(status=status_data.status))


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client: models.Client = Depends(get_client_or_404),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(Role.ADMIN)),
):
    """Admins only. Also deletes the client's deals and their tasks."""
    crud.delete_client(db, client)
