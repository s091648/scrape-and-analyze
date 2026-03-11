#!/usr/bin/env python3
"""
Create an admin user in the database.

Usage:
    python scripts/create_admin.py
    ADMIN_USERNAME=admin ADMIN_PASSWORD=secret ADMIN_EMAIL=a@b.com python scripts/create_admin.py
"""
import os
import sys
import uuid

# Allow running from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    import bcrypt
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    username = os.environ.get("ADMIN_USERNAME") or input("Username [admin]: ").strip() or "admin"
    password = os.environ.get("ADMIN_PASSWORD") or input("Password: ").strip()
    email = os.environ.get("ADMIN_EMAIL") or input("Email (optional): ").strip() or None
    name = os.environ.get("ADMIN_NAME") or input("Display name (optional): ").strip() or None

    if not password:
        print("ERROR: password required")
        sys.exit(1)

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        from models.auth import User
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"User '{username}' already exists. Updating role to admin.")
            existing.role = 'admin'
            existing.is_allowed = True
            db.commit()
        else:
            user = User(
                id=uuid.uuid4(),
                username=username,
                hashed_password=hashed,
                email=email if email else None,
                name=name if name else None,
                role='admin',
                is_allowed=True,
            )
            db.add(user)
            db.commit()
            print(f"✓ Admin user '{username}' created successfully.")
    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
