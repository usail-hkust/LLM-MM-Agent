"""
Database configuration - Async SQLAlchemy engine and session factory.
"""
from pathlib import Path
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings


def _ensure_sqlite_parent() -> None:
    if not settings.DATABASE_URL.startswith("sqlite"):
        return
    sqlite_target = settings.DATABASE_URL.split("///", 1)[-1]
    if not sqlite_target or sqlite_target == ":memory:":
        return
    Path(sqlite_target).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_parent()

# Create Async Engine
# [FIX] echo=False explicitly to prevent stdout noise overriding logging config.
# Use logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO) if SQL logs are needed.
# [Local-first] SQLite does not support the same pool arguments as PostgreSQL.
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        future=True,
    )
else:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        future=True,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_pre_ping=True,
        pool_recycle=settings.DB_POOL_RECYCLE,
    )

# Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async session."""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """Initialize tables and seed local auth state when needed."""
    from sqlmodel import SQLModel
    from sqlalchemy import select
    # Import models to ensure they are registered
    from app.infra.persistence.models import (
        ProjectDB, 
        NodeVersionDB, 
        NodeStateDB, 
        CopilotSessionDB, 
        CopilotMessageDB,
        UserDB, 
        InvitationCodeDB
    )  # noqa
    from app.core.security import get_password_hash
    
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        
    async with AsyncSessionLocal() as session:
        changed = False

        if settings.SEED_LOCAL_ADMIN:
            admin_result = await session.execute(
                select(UserDB).where(UserDB.email == settings.LOCAL_ADMIN_EMAIL)
            )
            if not admin_result.scalar_one_or_none():
                session.add(
                    UserDB(
                        id="local-admin",
                        email=settings.LOCAL_ADMIN_EMAIL,
                        hashed_password=get_password_hash(settings.LOCAL_ADMIN_PASSWORD),
                        is_active=True,
                        is_superuser=True,
                    )
                )
                changed = True

        if settings.REQUIRE_INVITE_CODE:
            code_result = await session.execute(select(InvitationCodeDB).limit(1))
            if not code_result.scalar_one_or_none():
                session.add(InvitationCodeDB(code="LOCAL-SETUP"))
                changed = True

        if changed:
            await session.commit()
