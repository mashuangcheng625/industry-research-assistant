"""Create the non-login source owner and four semiconductor knowledge bases."""
from __future__ import annotations

import argparse
import secrets

from core.database import SessionLocal
from core.security import get_password_hash
from models.user import User
from scripts.seed_semiconductor_knowledge_bases import seed_knowledge_bases


def ensure_service_user(username: str, email: str) -> bool:
    """Create an inactive service owner without printing or persisting a password."""
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            return False
        email_owner = db.query(User).filter(User.email == email).first()
        if email_owner:
            raise ValueError(f"邮箱已属于其他用户: {email}")
        db.add(User(
            username=username,
            email=email,
            hashed_password=get_password_hash(secrets.token_urlsafe(48)),
            is_active=False,
            is_superuser=False,
        ))
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default="source_pipeline")
    parser.add_argument(
        "--email",
        default="source-pipeline@localhost.invalid",
        help="Unique technical email; the account remains disabled for login.",
    )
    args = parser.parse_args()

    user_created = ensure_service_user(args.username, args.email)
    created, existing = seed_knowledge_bases(args.username)
    print({
        "username": args.username,
        "user_created": user_created,
        "login_enabled": False,
        "knowledge_bases_created": created,
        "knowledge_bases_existing": existing,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
