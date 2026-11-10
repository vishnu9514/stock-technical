from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from kpi.database import initialize_database
from kpi.models import Base, BugTracking, DevelopmentRelease


def test_release_bug_relationship_and_database_catalog_seed():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        initialize_database(session)
        release = DevelopmentRelease(
            project_id="sample",
            release_key="v1",
            released_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        session.add(release)
        session.flush()
        bug = BugTracking(
            project_id="sample",
            external_key="issue-1",
            release_id=release.id,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        session.add(bug)
        session.commit()
        assert release.bugs[0].external_key == "issue-1"
        assert session.get(BugTracking, bug.id).release.release_key == "v1"
    engine.dispose()
