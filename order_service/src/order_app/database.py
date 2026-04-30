import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncAttrs
from sqlalchemy.orm import DeclarativeBase

env_path = Path(__file__).resolve().parents[3] / ".env"

if env_path.exists():
    load_dotenv(dotenv_path="/app/.env")
else:
    logging.warning(f"⚠️ .env file not found at {env_path}")


DATABASE_URL = os.getenv("ORDERS_DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("❌ CRITICAL: ORDER_DATABASE_URL is not set in the environment.")

engine = create_async_engine(
    DATABASE_URL,
    # echo=True is for debugging only
    echo=False,
    # Connection Pooling: Essential for preventing 'Too many connections' errors
    pool_size=10,           # Keep 10 connections open
    max_overflow=20,        # Allow up to 20 extra if traffic spikes
    pool_timeout=30,        # Wait 30s for a connection before failing
    pool_recycle=1800,      # Recycle connections every 30 mins to prevent stale links
)


AsyncSessionLocal = async_sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False,
    autoflush=False
)


class Base(AsyncAttrs, DeclarativeBase):
    pass


async def get_db():
    """Dependency to provide an async session for FastAPI routes."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
        
async def init_db():
    """Initializes the database schema."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)