"""
Creates the admin user from environment variables.
Usage: uv run python scripts/seed_user.py
Env vars: SEED_EMAIL, SEED_PASSWORD (falls back to .env defaults)
"""
import asyncio
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth.session import hash_password
from app.config import settings
from app.models.user import User


async def main() -> None:
    email = os.getenv("SEED_EMAIL", "admin@example.com")
    password = os.getenv("SEED_PASSWORD", "changeme123!")

    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        existing = await session.scalar(select(User).where(User.email == email))
        if existing:
            print(f"User {email} already exists — skipping.")
        else:
            user = User(email=email, password_hash=hash_password(password))
            session.add(user)
            await session.commit()
            print(f"Created user: {email}")

    await engine.dispose()


asyncio.run(main())
