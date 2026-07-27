"""Create (or verify) a local system_admin user.

This script is never run automatically — it must be invoked manually, and
only by someone who already has access to the local database. It does not
expose an API endpoint; there is no public way to create a system_admin
account.

Usage (inside the backend container), via environment variables:

    docker compose exec \
      -e ADMIN_EMAIL=admin@example.com \
      -e ADMIN_NAME="System Admin" \
      -e ADMIN_PASSWORD=<a-real-local-only-password> \
      backend python scripts/create_system_admin.py

Or via CLI arguments:

    docker compose exec backend python scripts/create_system_admin.py \
      --email admin@example.com --name "System Admin" --password <password>

The password is never printed, logged, or echoed back. Re-running this
script with the same email is safe: if that user already exists with role
`system_admin`, nothing changes. If that email belongs to a different
existing user (or a user with a different role), the script refuses to
modify it and exits with an error instead of silently overwriting anything.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.auth.password import hash_password  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a local system_admin user.")
    parser.add_argument("--email", default=os.environ.get("ADMIN_EMAIL"))
    parser.add_argument("--name", default=os.environ.get("ADMIN_NAME"))
    parser.add_argument("--password", default=os.environ.get("ADMIN_PASSWORD"))
    args = parser.parse_args()

    if not args.email or not args.name or not args.password:
        print(
            "Missing required admin email, name, or password. Provide them via "
            "ADMIN_EMAIL / ADMIN_NAME / ADMIN_PASSWORD environment variables, or "
            "--email / --name / --password CLI arguments.",
            file=sys.stderr,
        )
        sys.exit(1)

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == args.email).first()
        if existing:
            if existing.role == UserRole.SYSTEM_ADMIN.value:
                print(
                    f"[create_system_admin] User '{args.email}' already exists "
                    f"with role '{UserRole.SYSTEM_ADMIN.value}'. No changes made."
                )
                return
            print(
                f"[create_system_admin] Refusing to modify existing user "
                f"'{args.email}' (current role: '{existing.role}'). This script "
                f"will not overwrite an existing user that isn't already a "
                f"system_admin.",
                file=sys.stderr,
            )
            sys.exit(1)

        admin = User(
            name=args.name,
            email=args.email,
            password_hash=hash_password(args.password),
            role=UserRole.SYSTEM_ADMIN.value,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        print(
            f"[create_system_admin] Created system_admin user '{args.email}' "
            f"(id={admin.id})."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
