"""Reusable FastAPI dependencies: authentication, roles and record lookup."""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

import crud
import models
import security
from database import get_db
from enums import Role

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = security.decode_access_token(token)
        subject = payload.get("sub")
        if subject is None:
            raise credentials_exception
        # Old tokens carried the username in "sub". int() fails on them,
        # which is exactly what we want: such a token is no longer valid.
        user_id = int(subject)
    except (jwt.PyJWTError, TypeError, ValueError):
        raise credentials_exception

    user = crud.get_user(db, user_id)
    if user is None:
        raise credentials_exception
    return user


def require_role(*allowed_roles: str):
    """
    Usage in a route:
        current_user: models.User = Depends(require_role(Role.ADMIN))
    Lets through only users with one of the given roles.
    """

    def role_checker(current_user: models.User = Depends(get_current_user)) -> models.User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission for this action",
            )
        return current_user

    return role_checker


def owner_scope(current_user: models.User):
    """None for admins (no filter), the manager's id for everyone else."""
    if current_user.role == Role.ADMIN:
        return None
    return current_user.id


def ensure_owner_or_admin(current_user: models.User, owner_id) -> None:
    """
    A manager may only touch their own records or unassigned ones.

    Returns 404 rather than 403: the API should not even confirm that a
    record belonging to someone else exists.
    """
    if current_user.role == Role.ADMIN:
        return
    if owner_id is not None and owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")


def get_client_or_404(client_id: int, db: Session = Depends(get_db)) -> models.Client:
    client = crud.get_client(db, client_id)
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return client


def get_deal_or_404(deal_id: int, db: Session = Depends(get_db)) -> models.Deal:
    deal = crud.get_deal(db, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return deal


def get_task_or_404(task_id: int, db: Session = Depends(get_db)) -> models.Task:
    task = crud.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task
