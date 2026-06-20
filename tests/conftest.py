import os
import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from app.db import Base, get_db
from app.main import app
from app.models import AdminUser, Customer, License, LicensePlan
from app.services.auth_service import hash_password


@pytest.fixture()
def test_db_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(test_db_session: Session):
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)


@pytest.fixture()
def seeded_license(test_db_session: Session, now_utc: dt.datetime) -> License:
    plan = LicensePlan(code="monthly", name="Monthly", price_eur=9.99, duration_days=30, is_active=True, is_trial=False)
    customer = Customer(email="tester@example.com", full_name="Tester")
    test_db_session.add(plan)
    test_db_session.add(customer)
    test_db_session.commit()

    license_obj = License(
        key="LIC-TEST-12345678",
        plan_code=plan.code,
        is_active=True,
        expires_at=now_utc + dt.timedelta(days=30),
        created_at=now_utc,
        customer_id=customer.id,
    )
    test_db_session.add(license_obj)
    test_db_session.commit()
    test_db_session.refresh(license_obj)

    return license_obj


@pytest.fixture()
def expired_license(test_db_session: Session, now_utc: dt.datetime) -> License:
    plan = LicensePlan(code="monthly-exp", name="Monthly Exp", price_eur=9.99, duration_days=30, is_active=True, is_trial=False)
    customer = Customer(email="expired@example.com", full_name="Expired User")
    test_db_session.add(plan)
    test_db_session.add(customer)
    test_db_session.commit()

    license_obj = License(
        key="LIC-EXPIRED-12345678",
        plan_code=plan.code,
        is_active=True,
        expires_at=now_utc - dt.timedelta(days=1),
        created_at=now_utc - dt.timedelta(days=31),
        customer_id=customer.id,
    )
    test_db_session.add(license_obj)
    test_db_session.commit()
    test_db_session.refresh(license_obj)
    return license_obj


@pytest.fixture()
def inactive_license(test_db_session: Session, now_utc: dt.datetime) -> License:
    plan = LicensePlan(code="monthly-ina", name="Monthly Ina", price_eur=9.99, duration_days=30, is_active=True, is_trial=False)
    customer = Customer(email="inactive@example.com", full_name="Inactive User")
    test_db_session.add(plan)
    test_db_session.add(customer)
    test_db_session.commit()

    license_obj = License(
        key="LIC-INACTIVE-12345678",
        plan_code=plan.code,
        is_active=False,
        expires_at=now_utc + dt.timedelta(days=30),
        created_at=now_utc,
        customer_id=customer.id,
    )
    test_db_session.add(license_obj)
    test_db_session.commit()
    test_db_session.refresh(license_obj)
    return license_obj


@pytest.fixture()
def trial_plan(test_db_session: Session) -> LicensePlan:
    plan = LicensePlan(code="trial5", name="Trial 5 Days", price_eur=0.0, duration_days=5, is_active=True, is_trial=True)
    test_db_session.add(plan)
    test_db_session.commit()
    test_db_session.refresh(plan)
    return plan


@pytest.fixture()
def superadmin_user(test_db_session: Session) -> AdminUser:
    user = AdminUser(
        username="testadmin",
        password_hash=hash_password("SecurePass1!"),
        role="superadmin",
        is_active=True,
    )
    test_db_session.add(user)
    test_db_session.commit()
    test_db_session.refresh(user)
    return user


@pytest.fixture()
def support_user(test_db_session: Session) -> AdminUser:
    user = AdminUser(
        username="testsupport",
        password_hash=hash_password("SecurePass2!"),
        role="support",
        is_active=True,
    )
    test_db_session.add(user)
    test_db_session.commit()
    test_db_session.refresh(user)
    return user
