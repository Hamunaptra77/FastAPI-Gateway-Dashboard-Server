import datetime as dt
import logging

from sqlalchemy.orm import Session

from app.models import LicenseRenewalOrder
from app.services.license_service import extend_license, get_plan_by_code

logger = logging.getLogger(__name__)


def process_renewal_capture(db: Session, renewal: LicenseRenewalOrder, capture: dict) -> None:
    renewal.status = capture.get("status", renewal.status)

    captures = (
        capture.get("purchase_units", [{}])[0]
        .get("payments", {})
        .get("captures", [])
    )
    if captures:
        renewal.paypal_capture_id = captures[0].get("id")

    if renewal.status in {"COMPLETED", "APPROVED"} and not renewal.is_processed:
        plan = get_plan_by_code(db, renewal.plan_code)
        if not plan:
            logger.error(
                "renewal_plan_not_found renewal_id=%s plan_code=%s",
                renewal.id,
                renewal.plan_code,
            )
        else:
            extend_license(db, renewal.license, plan)
        renewal.is_processed = True
        renewal.processed_at = dt.datetime.now(dt.UTC).replace(tzinfo=None)

    db.add(renewal)
    db.commit()
