from __future__ import annotations

import os
from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .metrics import DEFINITIONS
from .models import Base, KpiMaster


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker[Session]:
    url = os.environ.get("KPI_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "KPI_DATABASE_URL is not set. Configure a PostgreSQL SQLAlchemy URL, "
            "for example postgresql+psycopg://user:password@host:5432/database."
        )
    return sessionmaker(bind=create_engine(url, pool_pre_ping=True), expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    session = _session_factory()()
    try:
        yield session
    finally:
        session.close()


def initialize_database(session: Session) -> None:
    """Create the declared tables and idempotently seed the KPI definitions."""
    Base.metadata.create_all(session.get_bind())
    for definition in DEFINITIONS:
        if session.get(KpiMaster, definition.id) is None:
            session.add(
                KpiMaster(
                    id=definition.id,
                    area=definition.area,
                    name=definition.name,
                    description=definition.description,
                    what_it_measures=definition.what_it_measures,
                    formula=definition.formula,
                    direction=definition.direction.value,
                    frequency=definition.frequency,
                    data_source=definition.data_source,
                )
            )
    session.commit()
