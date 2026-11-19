from fastapi import APIRouter, Depends, Form, HTTPException, status
from sqlalchemy.orm import Session

import crud
import models
import schemas
import security
from database import get_db
from dependencies import require_role
from enums import Role

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(Role.ADMIN)),
):
    """
    Create a new employee account. Admins only.

    Open self-registration would let anyone on the internet create a manager
    account and read every unassigned client. The very first admin is created
    with create_admin.py on the server.
    """
    if crud.get_user_by_username(db, user.username):
        raise HTTPException(status_code=400, detail="A user with this username already exists")
    return crud.create_user(db, user)


@router.post("/login", response_model=schemas.Token)
def login_user(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = crud.get_user_by_username(db, username.strip())
    if not user or not security.verify_password(password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    return {"access_token": security.create_access_token(user.id), "token_type": "bearer"}
