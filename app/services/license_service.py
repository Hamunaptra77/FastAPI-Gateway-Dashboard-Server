import datetime as dt

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Customer, License, LicensePlan, generate_license_key


def get_or_create_customer(db: Session, email: str, full_name: str) -> Customer:
    normalized_email = email.lower().strip()
    customer = db.query(Customer).filter(Customer.email == normalized_email).first()
    if customer:
        if full_name and customer.full_name != full_name:
            customer.full_name = full_name
            db.add(customer)
            db.commit()
            db.refresh(customer)
        return customer

    customer = Customer(email=normalized_email, full_name=full_name)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def seed_license_plans(db: Session) -> None:
    plan_specs = [
        ("trial5", "Trial 5 Days", 0.0, 5, True),
        ("monthly", "Monthly", settings.plan_monthly_price_eur, 30, False),
        ("yearly", "Yearly", settings.plan_yearly_price_eur, 365, False),
        ("lifetime", "Lifetime", settings.plan_lifetime_price_eur, None, False),
    ]

    for code, name, price, duration, is_trial in plan_specs:
        existing = db.query(LicensePlan).filter(LicensePlan.code == code).first()
        if existing:
            continue
        db.add(
            LicensePlan(
                code=code,
                name=name,
                price_eur=price,
                duration_days=duration,
                is_active=True,
                is_trial=is_trial,
            )
        )
    db.commit()


def get_active_plans(db: Session) -> list[LicensePlan]:
    return db.query(LicensePlan).filter(LicensePlan.is_active.is_(True)).order_by(LicensePlan.price_eur.asc()).all()


def get_plan_by_code(db: Session, plan_code: str) -> LicensePlan | None:
    return db.query(LicensePlan).filter(LicensePlan.code == plan_code, LicensePlan.is_active.is_(True)).first()


def issue_license(db: Session, customer: Customer, plan: LicensePlan) -> License:
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    expires = None
    if plan.duration_days is not None:
        expires = now + dt.timedelta(days=plan.duration_days)

    license_obj = License(
        key=generate_license_key(),
        customer_id=customer.id,
        plan_code=plan.code,
        is_active=True,
        expires_at=expires,
    )
    db.add(license_obj)
    db.commit()
    db.refresh(license_obj)
    return license_obj


def extend_license(db: Session, license_obj: License, plan: LicensePlan) -> License:
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)

    if plan.duration_days is None:
        license_obj.expires_at = None
        license_obj.is_active = True
    else:
        if license_obj.expires_at is None:
            base = now
        else:
            base = license_obj.expires_at if license_obj.expires_at > now else now

        license_obj.expires_at = base + dt.timedelta(days=plan.duration_days)
        license_obj.is_active = True

    db.add(license_obj)
    db.commit()
    db.refresh(license_obj)
    return license_obj


def validate_license_key(db: Session, key: str) -> tuple[bool, str | None, dt.datetime | None, str | None]:
    license_obj = db.query(License).filter(License.key == key).first()
    if not license_obj:
        return False, None, None, "license_not_found"

    if not license_obj.is_active:
        return False, license_obj.customer.email, license_obj.expires_at, "license_inactive"

    if license_obj.expires_at is not None and license_obj.expires_at < dt.datetime.now(dt.UTC).replace(tzinfo=None):
        return False, license_obj.customer.email, license_obj.expires_at, "license_expired"

    return True, license_obj.customer.email, license_obj.expires_at, None
