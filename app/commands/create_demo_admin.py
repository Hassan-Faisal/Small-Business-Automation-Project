from __future__ import annotations

import argparse
import getpass
import sys

import bcrypt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.database import dispose_database_resources, get_session_factory
from app.core.security import normalize_email
from app.models.admin_user import AdminUser


def hash_demo_password(password: str) -> str:
    if len(password) < 4:
        raise ValueError("Demo password must be at least 4 characters long.")

    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a TiffinAI demo admin account."
    )
    parser.add_argument("--full-name")
    parser.add_argument("--email")
    args = parser.parse_args()

    full_name = (
        args.full_name or input("Demo user full name: ")
    ).strip()

    email = normalize_email(
        args.email or input("Demo email: ")
    )

    password = getpass.getpass("Demo password: ")
    confirmation = getpass.getpass("Confirm demo password: ")

    if not full_name:
        print(
            "Creation failed: full name is required.",
            file=sys.stderr,
        )
        return 1

    if (
        "@" not in email
        or "."
        not in email.rsplit("@", 1)[-1]
    ):
        print(
            "Creation failed: enter a valid email address.",
            file=sys.stderr,
        )
        return 1

    if password != confirmation:
        print(
            "Creation failed: passwords do not match.",
            file=sys.stderr,
        )
        return 1

    try:
        hashed_password = hash_demo_password(password)
    except ValueError as exc:
        print(
            f"Creation failed: {exc}",
            file=sys.stderr,
        )
        return 1

    session = get_session_factory()()

    try:
        existing_admin = session.scalar(
            select(AdminUser).where(
                AdminUser.email == email
            )
        )

        if existing_admin is not None:
            print(
                "Creation failed: an admin with "
                "that email already exists.",
                file=sys.stderr,
            )
            return 1

        session.add(
            AdminUser(
                full_name=full_name,
                email=email,
                hashed_password=hashed_password,
                role="owner",
                is_active=True,
            )
        )

        session.commit()

        print(
            f"Demo admin created successfully for {email}."
        )

        return 0

    except IntegrityError:
        session.rollback()

        print(
            "Creation failed: an admin with "
            "that email already exists.",
            file=sys.stderr,
        )

        return 1

    except SQLAlchemyError as exc:
        session.rollback()

        print(
            f"Creation failed: database error "
            f"({exc.__class__.__name__}).",
            file=sys.stderr,
        )

        return 1

    finally:
        session.close()
        dispose_database_resources()


if __name__ == "__main__":
    raise SystemExit(main())