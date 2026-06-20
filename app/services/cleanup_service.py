import datetime as dt

from sqlalchemy.orm import Session

from app.config import settings
from app.models import License, TrialCleanupLog


def cleanup_inactive_trial_licenses(db: Session) -> int:
    cutoff = dt.datetime.now(dt.UTC).replace(tzinfo=None) - dt.timedelta(days=settings.trial_inactive_delete_after_days)

    deleted = (
        db.query(License)
        .filter(
            License.plan_code == "trial5",
            License.is_active.is_(False),
            License.created_at <= cutoff,
        )
        .delete(synchronize_session=False)
    )

    if deleted:
        db.add(TrialCleanupLog(deleted_count=deleted))

    db.commit()

    return deleted
