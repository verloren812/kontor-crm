from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

import crud
import models
import schemas
from database import get_db
from dependencies import ensure_owner_or_admin, get_current_user, get_task_or_404, owner_scope

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


@router.post("/", response_model=schemas.TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    task: schemas.TaskCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    deal = crud.get_deal(db, task.deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    ensure_owner_or_admin(current_user, deal.owner_id)
    created = crud.create_task(db, task)
    return crud.get_task(db, created.id)


@router.get("/", response_model=list[schemas.TaskResponse])
def get_all_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    deal_id: Optional[int] = None,
    is_done: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.get_tasks(
        db,
        skip=skip,
        limit=limit,
        deal_id=deal_id,
        is_done=is_done,
        owner_id=owner_scope(current_user),
    )


@router.get("/{task_id}", response_model=schemas.TaskResponse)
def get_task(
    task: models.Task = Depends(get_task_or_404),
    current_user: models.User = Depends(get_current_user),
):
    ensure_owner_or_admin(current_user, task.deal.owner_id)
    return task


@router.patch("/{task_id}", response_model=schemas.TaskResponse)
def update_task(
    data: schemas.TaskUpdate,
    task: models.Task = Depends(get_task_or_404),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ensure_owner_or_admin(current_user, task.deal.owner_id)
    return crud.update_task(db, task, data)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task: models.Task = Depends(get_task_or_404),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ensure_owner_or_admin(current_user, task.deal.owner_id)
    crud.delete_task(db, task)
