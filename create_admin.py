"""
Create the first administrator.

Run once on the server, never from the web UI. This is the only way to create
the very first admin; after that, admins manage roles in the Team page
(PATCH /api/users/{id}/role).

Usage:
    python create_admin.py
"""
import getpass

import models
import schemas
import security
from database import SessionLocal
from enums import Role


def main() -> None:
    db = SessionLocal()
    try:
        username = input("Admin username: ").strip()
        if len(username) < 3:
            print("The username must be at least 3 characters long.")
            return

        existing = db.query(models.User).filter(models.User.username == username).first()
        if existing:
            print(f"User '{username}' already exists (role: {existing.role}).")
            if input("Make this user an admin? (y/n): ").strip().lower() == "y":
                existing.role = Role.ADMIN.value
                db.commit()
                print(f"Done: '{username}' is now an admin.")
            return

        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Repeat password: "):
            print("The passwords do not match.")
            return
        try:
            schemas.UserCreate(username=username, password=password, role=Role.ADMIN)
        except ValueError as error:  # same rules as the API: length, 72-byte bcrypt limit
            print(error)
            return

        db.add(
            models.User(
                username=username,
                hashed_password=security.get_password_hash(password),
                role=Role.ADMIN.value,
            )
        )
        db.commit()
        print(f"Done: admin '{username}' created.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
