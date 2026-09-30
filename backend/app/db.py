"""SQLAlchemy engine and request-scoped session management."""

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.getenv("SIGES_DATABASE_URL", "sqlite:///./sig_es_dev.db")
if not DATABASE_URL.startswith(("sqlite:", "postgresql+psycopg://")):
    raise RuntimeError(
        "SIGES_DATABASE_URL deve usar sqlite:// ou postgresql+psycopg://"
    )

engine_options: dict[str, object] = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    """Yield one database session per API request and always close it."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
