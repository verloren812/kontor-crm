"""
Authentication and employee accounts.

Covers three fixed security issues:
  * registration used to be open to anyone;
  * the token carried the username instead of the immutable user id;
  * passwords had no length rules.
"""
import jwt
import pytest

import security
from conftest import ADMIN_PASSWORD, auth_header
from enums import Role

NEW_USER = {"username": "newbie", "password": "long-enough-password"}


# --- who may create employees ---

def test_registration_without_token_is_rejected(client):
    """The key point: a stranger cannot create an account for themselves."""
    response = client.post("/api/auth/register", json=NEW_USER)
    assert response.status_code == 401


def test_manager_cannot_register_users(client, manager_header):
    response = client.post("/api/auth/register", json=NEW_USER, headers=manager_header)
    assert response.status_code == 403


def test_admin_creates_manager(client, admin_header):
    response = client.post("/api/auth/register", json=NEW_USER, headers=admin_header)
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "newbie"
    assert body["role"] == Role.MANAGER.value
    assert "hashed_password" not in body


def test_admin_creates_another_admin(client, admin_header):
    response = client.post("/api/auth/register", json={**NEW_USER, "role": "admin"}, headers=admin_header)
    assert response.status_code == 201
    assert response.json()["role"] == Role.ADMIN.value


def test_unknown_role_is_rejected(client, admin_header):
    response = client.post("/api/auth/register", json={**NEW_USER, "role": "superuser"}, headers=admin_header)
    assert response.status_code == 422


def test_duplicate_username(client, admin_header, manager):
    response = client.post(
        "/api/auth/register",
        json={"username": manager.username, "password": "long-enough-password"},
        headers=admin_header,
    )
    assert response.status_code == 400


# --- password and username rules ---

@pytest.mark.parametrize(
    "password",
    [
        "short77",   # 7 characters, one below the minimum
        "",
        "a" * 73,    # bcrypt would silently ignore everything after 72 bytes
        "ä" * 40,    # 80 bytes in UTF-8 although only 40 characters
    ],
)
def test_bad_password_is_rejected(client, admin_header, password):
    response = client.post(
        "/api/auth/register", json={"username": "someone", "password": password}, headers=admin_header
    )
    assert response.status_code == 422


def test_72_bytes_is_accepted(client, admin_header):
    response = client.post(
        "/api/auth/register", json={"username": "edge", "password": "a" * 72}, headers=admin_header
    )
    assert response.status_code == 201


def test_too_short_username_is_rejected(client, admin_header):
    response = client.post(
        "/api/auth/register",
        json={"username": "  a  ", "password": "long-enough-password"},
        headers=admin_header,
    )
    assert response.status_code == 422


def test_username_is_trimmed(client, admin_header):
    response = client.post(
        "/api/auth/register",
        json={"username": "  mueller  ", "password": "long-enough-password"},
        headers=admin_header,
    )
    assert response.status_code == 201
    assert response.json()["username"] == "mueller"


# --- login ---

def test_login_returns_token(client, admin):
    response = client.post("/api/auth/login", data={"username": admin.username, "password": ADMIN_PASSWORD})
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"


def test_login_with_wrong_password(client, admin):
    response = client.post("/api/auth/login", data={"username": admin.username, "password": "wrong-password"})
    assert response.status_code == 400


def test_login_with_unknown_user(client):
    response = client.post("/api/auth/login", data={"username": "nobody", "password": "whatever-123"})
    assert response.status_code == 400


# --- what is inside the token ---

def test_token_contains_id_not_username(client, admin):
    response = client.post("/api/auth/login", data={"username": admin.username, "password": ADMIN_PASSWORD})
    payload = jwt.decode(
        response.json()["access_token"],
        security.settings.secret_key,
        algorithms=[security.settings.algorithm],
    )
    assert payload["sub"] == str(admin.id)


def test_token_survives_rename(client, db, manager, manager_header):
    """Renaming a user must not log them out in the middle of the day."""
    manager.username = "anna-schmidt"
    db.commit()

    response = client.get("/api/users/me", headers=manager_header)
    assert response.status_code == 200
    assert response.json()["username"] == "anna-schmidt"


def test_legacy_token_with_username_is_invalid(client, manager):
    """
    Old-style token with the username in "sub". If that username were freed
    and taken by someone else, such a token must not grant access.
    """
    legacy_token = jwt.encode(
        {"sub": manager.username}, security.settings.secret_key, algorithm=security.settings.algorithm
    )
    response = client.get("/api/users/me", headers={"Authorization": f"Bearer {legacy_token}"})
    assert response.status_code == 401


def test_token_of_deleted_user_is_invalid(client, db, manager, manager_header):
    db.delete(manager)
    db.commit()
    assert client.get("/api/users/me", headers=manager_header).status_code == 401


def test_garbage_token(client):
    assert client.get("/api/users/me", headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_token_signed_with_other_key_is_invalid(client, manager):
    forged = jwt.encode({"sub": str(manager.id)}, "some-other-secret-key-of-enough-length", algorithm="HS256")
    assert client.get("/api/users/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_me_returns_current_user(client, manager):
    response = client.get("/api/users/me", headers=auth_header(manager))
    assert response.json()["role"] == "manager"
