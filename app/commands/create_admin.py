from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.database import dispose_database_resources, get_session_factory
from app.core.security import hash_password, normalize_email, validate_password_strength
from app.models.admin_user import AdminUser


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the first TiffinAI admin owner.")
    parser.add_argument("--full-name")
    parser.add_argument("--email")
    args = parser.parse_args()

    full_name = (args.full_name or input("Full name: ")).strip()
    email = normalize_email(args.email or input("Email: "))
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")

    if not full_name:
        print("Creation failed: full name is required.", file=sys.stderr)
        return 1
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        print("Creation failed: enter a valid email address.", file=sys.stderr)
        return 1
    if password != confirmation:
        print("Creation failed: passwords do not match.", file=sys.stderr)
        return 1
    try:
        hashed_password = hash_password(password)
    except ValueError as exc:
        print(f"Creation failed: {exc}", file=sys.stderr)
        return 1

    session = get_session_factory()()
    try:
        if session.scalar(select(AdminUser).where(AdminUser.email == email)) is not None:
            print("Creation failed: an admin with that email already exists.", file=sys.stderr)
            return 1
        session.add(AdminUser(full_name=full_name, email=email, hashed_password=hashed_password))
        session.commit()
        print(f"Admin owner created successfully for {email}.")
        return 0
    except IntegrityError:
        session.rollback()
        print("Creation failed: an admin with that email already exists.", file=sys.stderr)
        return 1
    except SQLAlchemyError as exc:
        session.rollback()
        print(f"Creation failed: database error ({exc.__class__.__name__}).", file=sys.stderr)
        return 1
    finally:
        session.close()
        dispose_database_resources()


if __name__ == "__main__":
    raise SystemExit(main())