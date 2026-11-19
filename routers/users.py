from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import crud
import models
import schemas
from database import get_db
from dependencies import get_current_user, require_role
from enums import Role

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/me", response_model=schemas.UserResponse)
def read_current_user(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.get("/", response_model=list[schemas.UserResponse])
def get_all_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(Role.ADMIN)),
):
    return crud.get_users(db, skip=skip, limit=limit)


@router.patch("/{user_id}/role", response_model=schemas.UserResponse)
def update_user_role(
    user_id: int,
    data: schemas.UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(Role.ADMIN)),
):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Lock-out protection: without these checks an admin could demote
    # themselves and nobody would be left who is allowed to assign roles.
    if user.id == current_user.id and data.role != Role.ADMIN:
        raise HTTPException(status_code=400, detail="You cannot remove the admin role from yourself")
    if user.role == Role.ADMIN and data.role != Role.ADMIN and crud.count_admins(db) <= 1:
        raise HTTPException(status_code=400, detail="At least one admin must remain")

    return crud.update_user_role(db, user, Role(data.role).value)
