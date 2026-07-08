from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from src.database import SessionLocal
from src.models import Payment


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def add_payment(
    tenant_id: int,
    property_id: int,
    amount: Decimal | float | str,
    currency: str = "ZAR",
    due_date: datetime | None = None,
    status: str = "pending",
    paid_at: datetime | None = None,
    reference: str | None = None,
) -> Payment:
    """Add a new payment record to the database."""
    payment = Payment(
        tenant_id=tenant_id,
        property_id=property_id,
        amount=Decimal(str(amount)),
        currency=currency,
        status=status,
        due_date=_normalize_datetime(due_date),
        paid_at=_normalize_datetime(paid_at),
        reference=reference,
    )

    with SessionLocal() as session:
        session.add(payment)
        session.commit()
        session.refresh(payment)

    return payment


def list_payments() -> list[Payment]:
    """Retrieve all payment records."""
    with SessionLocal() as session:
        return session.scalars(select(Payment)).all()


def get_payment_by_id(payment_id: int) -> Payment | None:
    """Retrieve a specific payment by its ID."""
    with SessionLocal() as session:
        return session.get(Payment, payment_id)


def get_payments_by_tenant(tenant_id: int) -> list[Payment]:
    """Retrieve all payments associated with a specific tenant."""
    with SessionLocal() as session:
        return session.scalars(
            select(Payment).where(Payment.tenant_id == tenant_id)
        ).all()


def is_late(payment: Payment) -> bool:
    """
    Check if a payment is overdue.
    A payment is late if it is not 'paid' and the current time is past the due date.
    """
    if payment.status == "paid":
        return False

    due_date = _normalize_datetime(payment.due_date)
    if not due_date:
        return False

    return datetime.now(timezone.utc) > due_date


def get_overdue_payments() -> list[Payment]:
    """Retrieve all payments that are currently overdue."""
    with SessionLocal() as session:
        # Filter for potentially overdue statuses first for performance
        payments = session.scalars(
            select(Payment).where(Payment.status.in_(["pending", "overdue"]))
        ).all()
        return [p for p in payments if is_late(p)]


def mark_payment_as_paid(payment_id: int) -> Payment | None:
    """Mark a payment as paid and set the payment timestamp to now."""
    with SessionLocal() as session:
        payment = session.get(Payment, payment_id)
        if payment:
            payment.status = "paid"
            payment.paid_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(payment)

    return payment


def update_payment_status(payment_id: int, status: str) -> Payment | None:
    """Update the status of a payment (e.g., from 'pending' to 'overdue')."""
    with SessionLocal() as session:
        payment = session.get(Payment, payment_id)
        if payment:
            payment.status = status
            session.commit()
            session.refresh(payment)

    return payment


def get_tenant_payment_summary(tenant_id: int) -> dict[str, Any]:
    """
    Generate a financial summary for a specific tenant,
    including total-owed, total paid, and overdue counts.
    """
    payments = get_payments_by_tenant(tenant_id)

    total_owed = sum(p.amount for p in payments if p.status != "paid")
    total_paid = sum(p.amount for p in payments if p.status == "paid")
    overdue_count = sum(1 for p in payments if is_late(p))

    return {
        "tenant_id": tenant_id,
        "total_owed": total_owed,
        "total_paid": total_paid,
        "overdue_count": overdue_count,
        "payment_count": len(payments),
    }