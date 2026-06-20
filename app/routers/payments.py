from typing import Any
import datetime as dt
import ipaddress
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import License, LicenseRenewalOrder, Payment, TrialRequestLog
from app.schemas import CreateCheckoutRequest, CreateCheckoutResponse, CreateTrialRequest, CreateTrialResponse
from app.services.email_service import send_license_email
from app.services.license_service import get_or_create_customer, get_plan_by_code, issue_license
from app.services.paypal_service import PayPalError, PayPalService
from app.services.renewal_service import process_renewal_capture

router = APIRouter(prefix="/api/payments", tags=["payments"])
paypal = PayPalService()
logger = logging.getLogger(__name__)

# Trusted proxy CIDR ranges; extend via TRUSTED_PROXIES env var if needed.
_TRUSTED_PROXY_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.1/32"),
]


def _client_ip(request: Request) -> str:
    direct_ip = request.client.host if request.client else None
    try:
        direct_net = ipaddress.ip_address(direct_ip) if direct_ip else None
    except ValueError:
        direct_net = None

    # Only honour X-Forwarded-For when the direct connection comes from a trusted proxy.
    if direct_net and any(direct_net in net for net in _TRUSTED_PROXY_RANGES):
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if forwarded:
            try:
                ipaddress.ip_address(forwarded)
                return forwarded
            except ValueError:
                pass

    return direct_ip or "unknown"


def _enforce_trial_rate_limit(db: Session, ip_address: str, email: str) -> None:
    # Log the attempt FIRST, then check – otherwise the first attempt is never counted.
    db.add(TrialRequestLog(ip_address=ip_address, email=email.lower()))
    db.commit()

    window_start = dt.datetime.now(dt.UTC).replace(tzinfo=None) - dt.timedelta(
        seconds=settings.trial_rate_limit_window_seconds
    )

    request_count = (
        db.query(TrialRequestLog)
        .filter(
            TrialRequestLog.ip_address == ip_address,
            TrialRequestLog.created_at >= window_start,
        )
        .count()
    )

    if request_count > settings.trial_rate_limit_max_requests:
        raise HTTPException(status_code=429, detail="Too many trial requests. Please try again later.")


def finalize_payment_and_license(db: Session, payment: Payment) -> None:
    if payment.status not in {"COMPLETED", "APPROVED"}:
        return

    if payment.license_id is not None:
        return

    plan = get_plan_by_code(db, payment.plan_code)
    if not plan:
        logger.error("finalize_payment_plan_not_found payment_id=%s plan=%s", payment.id, payment.plan_code)
        return

    license_obj = issue_license(db, payment.customer, plan)
    payment.license_id = license_obj.id

    mail_ok, _ = send_license_email(payment.customer, license_obj)
    payment.email_sent = mail_ok
    if mail_ok:
        payment.email_sent_at = dt.datetime.now(dt.UTC).replace(tzinfo=None)

    db.add(payment)
    db.commit()
    logger.info("payment_finalized payment_id=%s license_id=%s email_sent=%s", payment.id, license_obj.id, mail_ok)


@router.post("/checkout", response_model=CreateCheckoutResponse)
def create_checkout(payload: CreateCheckoutRequest, db: Session = Depends(get_db)):
    customer = get_or_create_customer(db, payload.email, payload.full_name)
    plan = get_plan_by_code(db, payload.plan_code)
    if not plan:
        raise HTTPException(status_code=400, detail="Unknown or inactive plan")

    idempotency_key = str(uuid.uuid4())

    try:
        order = paypal.create_order(
            amount_eur=f"{plan.price_eur:.2f}",
            return_url=f"{settings.app_base_url}/api/payments/paypal/return",
            cancel_url=f"{settings.app_base_url}/api/payments/paypal/cancel",
            idempotency_key=idempotency_key,
        )
    except PayPalError as exc:
        logger.error("checkout_paypal_error %s", exc)
        raise HTTPException(status_code=502, detail="Payment service temporarily unavailable.") from exc

    approve_url = ""
    for link in order.get("links", []):
        if link.get("rel") == "approve":
            approve_url = link.get("href", "")
            break

    payment = Payment(
        paypal_order_id=order["id"],
        plan_code=plan.code,
        amount=plan.price_eur,
        currency="EUR",
        status=order.get("status", "CREATED"),
        customer_id=customer.id,
    )
    db.add(payment)
    db.commit()

    return CreateCheckoutResponse(order_id=order["id"], approve_url=approve_url)


@router.post("/trial", response_model=CreateTrialResponse)
def create_trial(payload: CreateTrialRequest, request: Request, db: Session = Depends(get_db)):
    _enforce_trial_rate_limit(db, _client_ip(request), payload.email)

    customer = get_or_create_customer(db, payload.email, payload.full_name)

    trial_plan = get_plan_by_code(db, "trial5")
    if not trial_plan:
        raise HTTPException(status_code=500, detail="Trial plan is not configured")

    existing_trial = (
        db.query(License)
        .filter(License.customer_id == customer.id, License.plan_code == trial_plan.code)
        .first()
    )
    if existing_trial:
        raise HTTPException(status_code=400, detail="Trial license already used")

    trial_license = issue_license(db, customer, trial_plan)
    return CreateTrialResponse(
        license_key=trial_license.key,
        expires_at=trial_license.expires_at,
    )


@router.get("/paypal/return")
def paypal_return(token: str, db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(Payment.paypal_order_id == token).first()
    renewal = db.query(LicenseRenewalOrder).filter(LicenseRenewalOrder.paypal_order_id == token).first()
    if not payment and not renewal:
        raise HTTPException(status_code=404, detail="Payment not found")

    try:
        capture = paypal.capture_order(token)
    except PayPalError as exc:
        logger.error("paypal_return_capture_error token=%s error=%s", token, exc)
        raise HTTPException(status_code=502, detail="Payment service temporarily unavailable.") from exc

    if payment:
        payment.status = capture.get("status", "COMPLETED")

        captures: list[dict[str, Any]] = (
            capture.get("purchase_units", [{}])[0]
            .get("payments", {})
            .get("captures", [])
        )
        if captures:
            payment.paypal_capture_id = captures[0].get("id")

        db.add(payment)
        db.commit()
        finalize_payment_and_license(db, payment)
        return RedirectResponse(url="/")

    process_renewal_capture(db, renewal, capture)
    return RedirectResponse(url="/license/dashboard?msg=renewed")


@router.get("/paypal/cancel")
def paypal_cancel():
    return {"message": "Payment cancelled"}


@router.post("/paypal/webhook")
async def paypal_webhook(request: Request, db: Session = Depends(get_db)):
    event = await request.json()

    try:
        valid = paypal.verify_webhook_signature(
            transmission_id=request.headers.get("paypal-transmission-id", ""),
            transmission_time=request.headers.get("paypal-transmission-time", ""),
            cert_url=request.headers.get("paypal-cert-url", ""),
            auth_algo=request.headers.get("paypal-auth-algo", ""),
            transmission_sig=request.headers.get("paypal-transmission-sig", ""),
            webhook_event=event,
            webhook_id=settings.paypal_webhook_id,
        )
    except PayPalError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not valid:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event_type = event.get("event_type", "")
    resource = event.get("resource", {})

    if event_type == "PAYMENT.CAPTURE.COMPLETED":
        order_id = resource.get("supplementary_data", {}).get("related_ids", {}).get("order_id")
        capture_id = resource.get("id")
        if order_id:
            payment = db.query(Payment).filter(Payment.paypal_order_id == order_id).first()
            if payment:
                payment.status = "COMPLETED"
                payment.paypal_capture_id = capture_id
                db.add(payment)
                db.commit()
                finalize_payment_and_license(db, payment)
            else:
                renewal = db.query(LicenseRenewalOrder).filter(LicenseRenewalOrder.paypal_order_id == order_id).first()
                if renewal and not renewal.is_processed:
                    capture_stub = {
                        "status": "COMPLETED",
                        "purchase_units": [
                            {
                                "payments": {
                                    "captures": [{"id": capture_id}]
                                }
                            }
                        ],
                    }
                    process_renewal_capture(db, renewal, capture_stub)

    return {"ok": True}
