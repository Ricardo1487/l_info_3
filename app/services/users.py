from typing import Optional, Dict, Any
from sqlalchemy import text
from app.config.database import SessionLocal
import bcrypt

ROLE_ADMIN = "ADMIN"
ROLE_HIWI = "HIWI"


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    with SessionLocal() as db:
        row = db.execute(
            text("SELECT id, username, email, password_hash, role FROM users WHERE email = :email"),
            {"email": email},
        ).mappings().first()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    with SessionLocal() as db:
        row = db.execute(
            text("SELECT id, username, email, password_hash, role FROM users WHERE id = :id"),
            {"id": user_id},
        ).mappings().first()
    return dict(row) if row else None


def list_users():
    with SessionLocal() as db:
        rows = db.execute(
            text("SELECT id, username, email, role FROM users ORDER BY username")
        ).mappings().all()
    return [dict(r) for r in rows]


def create_user(username: str, email: str, password: str, role: str = ROLE_HIWI) -> int:
    # prüfen, ob E-Mail schon vorhanden ist
    existing = get_user_by_email(email)
    if existing:
        raise ValueError("Ein Benutzer mit dieser E-Mail existiert bereits.")

    password_hash = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    with SessionLocal() as db:
        result = db.execute(
            text("""
                INSERT INTO users (username, email, password_hash, role)
                VALUES (:username, :email, :password_hash, :role)
                RETURNING id
            """),
            {
                "username": username,
                "email": email,
                "password_hash": password_hash,
                "role": role,
            },
        )
        new_id = result.scalar_one()
        db.commit()

    return new_id


def delete_user(user_id: int) -> None:
    with SessionLocal() as db:
        db.execute(
            text("DELETE FROM users WHERE id = :id"),
            {"id": user_id},
        )
        db.commit()


def update_password(user_id: int, new_password: str) -> None:
    new_hash = bcrypt.hashpw(
        new_password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    with SessionLocal() as db:
        db.execute(
            text("UPDATE users SET password_hash = :pw WHERE id = :id"),
            {"pw": new_hash, "id": user_id},
        )
        db.commit()
