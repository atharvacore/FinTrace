"""Command-line helpers.

    python -m app.cli create-user --email admin@example.com --name "Admin" --role admin

The password is read from the FINTRACE_NEW_USER_PASSWORD environment variable if set,
otherwise prompted for (never passed as a command-line argument, so it stays out of shell history).
"""

import argparse
import getpass
import os
import sys

from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.security import hash_password
from app.db import get_session_factory
from app.models import User
from app.models.enums import Role
from app.schemas.user import UserCreate
from app.services.audit import record_audit


def create_user(email: str, name: str, role: Role, password: str) -> int:
    # Same validation as the API, so the CLI cannot create accounts the API would reject.
    try:
        data = UserCreate(email=email, full_name=name, role=role, password=password)
    except ValidationError as exc:
        messages = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        raise SystemExit(f"Invalid user details: {messages}") from None
    email = data.email
    with get_session_factory()() as db:
        if db.scalar(select(User).where(func.lower(User.email) == email.lower())):
            raise SystemExit(f"User {email} already exists")
        user = User(
            email=email.lower(), full_name=name, role=role, password_hash=hash_password(password)
        )
        db.add(user)
        db.flush()
        record_audit(
            db,
            actor=None,
            action="user.created",
            entity_type="user",
            entity_id=user.id,
            after={"email": user.email, "role": role.value, "via": "cli"},
        )
        db.commit()
        return user.id


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    cu = sub.add_parser("create-user", help="Create a user account")
    cu.add_argument("--email", required=True)
    cu.add_argument("--name", required=True)
    cu.add_argument("--role", required=True, choices=[r.value for r in Role])
    args = parser.parse_args(argv)

    if args.command == "create-user":
        password = os.environ.get("FINTRACE_NEW_USER_PASSWORD") or getpass.getpass("Password: ")
        user_id = create_user(args.email, args.name, Role(args.role), password)
        print(f"Created user {args.email} (id={user_id}, role={args.role})")


if __name__ == "__main__":
    main(sys.argv[1:])
