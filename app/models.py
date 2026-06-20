import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utc_now_naive() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utc_now_naive)

    licenses: Mapped[list["License"]] = relationship(back_populates="customer")


class LicensePlan(Base):
    __tablename__ = "license_plans"

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    price_eur: Mapped[float] = mapped_column(Float)
    duration_days: Mapped[int | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_trial: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utc_now_naive)

    licenses: Mapped[list["License"]] = relationship(back_populates="plan")


class License(Base):
    __tablename__ = "licenses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    plan_code: Mapped[str] = mapped_column(ForeignKey("license_plans.code"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utc_now_naive)

    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    customer: Mapped[Customer] = relationship(back_populates="licenses")
    plan: Mapped[LicensePlan] = relationship(back_populates="licenses")

    __table_args__ = (
        Index("ix_licenses_customer_plan", "customer_id", "plan_code"),
        Index("ix_licenses_status", "is_active"),
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    paypal_order_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    paypal_capture_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    plan_code: Mapped[str] = mapped_column(ForeignKey("license_plans.code"), index=True)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="EUR")
    status: Mapped[str] = mapped_column(String(50), default="CREATED", index=True)
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    email_sent_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utc_now_naive)

    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    customer: Mapped[Customer] = relationship()

    license_id: Mapped[int | None] = mapped_column(ForeignKey("licenses.id"), nullable=True)
    license: Mapped[License | None] = relationship()
    plan: Mapped[LicensePlan] = relationship()


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utc_now_naive)
    last_login_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class AdminUiSettings(Base):
    __tablename__ = "admin_ui_settings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"), unique=True, index=True)
    theme: Mapped[str] = mapped_column(String(30), default="default")
    font_scale: Mapped[int] = mapped_column(Integer, default=100)
    header_name: Mapped[str] = mapped_column(String(60), default="")
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)


class AdminHeroContent(Base):
    __tablename__ = "admin_hero_content"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"), unique=True, index=True)
    control_center_title: Mapped[str] = mapped_column(String(60), default="")
    control_center_headline: Mapped[str] = mapped_column(String(180), default="")
    control_center_description: Mapped[str] = mapped_column(String(500), default="")
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)


class TrialRequestLog(Base):
    __tablename__ = "trial_request_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    ip_address: Mapped[str] = mapped_column(String(64), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utc_now_naive)


class TrialCleanupLog(Base):
    __tablename__ = "trial_cleanup_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    deleted_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utc_now_naive)


class LicenseRenewalOrder(Base):
    __tablename__ = "license_renewal_orders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    paypal_order_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    paypal_capture_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="CREATED")
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    processed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utc_now_naive)

    license_id: Mapped[int] = mapped_column(ForeignKey("licenses.id"), index=True)
    license: Mapped[License] = relationship()

    plan_code: Mapped[str] = mapped_column(ForeignKey("license_plans.code"), index=True)
    plan: Mapped[LicensePlan] = relationship()


def generate_license_key() -> str:
    return f"LIC-{uuid.uuid4().hex[:8].upper()}-{uuid.uuid4().hex[:8].upper()}"


class LicenseLoginAttempt(Base):
    __tablename__ = "license_login_attempts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    ip_address: Mapped[str] = mapped_column(String(64), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utc_now_naive)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    actor_username: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(120))
    target_type: Mapped[str] = mapped_column(String(60))
    target_id: Mapped[str] = mapped_column(String(120))
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utc_now_naive)
