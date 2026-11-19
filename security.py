from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: int) -> str:
    """
    "sub" holds the user id, not the username.

    With the username two things break: renaming a user invalidates all their
    tokens, and if a freed username is taken by someone else, an old token
    grants access to the new account. The id never changes.
    Per the JWT spec the value must be a string.
    """
    now = datetime.now(timezone.utc)
    to_encode = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
