from __future__ import annotations

from typing import Any

from sqlalchemy import select

from src.database import SessionLocal
from src.models import Tenant


def add_tenant(
    full_name: str,
    email: str | None = None,
    phone: str | None = None,
    unit_number: str | None = None,
    lease_start_date: str | None = None,
    lease_end_date: str | None = None,
    notes: str | None = None,
) -> Tenant:
    """Add a new tenant to the system."""
    tenant = Tenant(
        full_name=full_name,
        email=email,
        phone=phone,
        unit_number=unit_number,
        lease_start_date=lease_start_date,
        lease_end_date=lease_end_date,
        notes=notes,
    )

    with SessionLocal() as session:
        session.add(tenant)
        session.commit()
        session.refresh(tenant)

    return tenant


def list_tenants() -> list[Tenant]:
    """Retrieve all tenants in the system."""
    with SessionLocal() as session:
        return session.scalars(select(Tenant)).all()


def get_tenant_by_id(tenant_id: int) -> Tenant | None:
    """Retrieve a tenant by their unique ID."""
    with SessionLocal() as session:
        return session.get(Tenant, tenant_id)


def get_tenant_by_email(email: str) -> Tenant | None:
    """Retrieve a tenant by their email address."""
    with SessionLocal() as session:
        return session.scalar(select(Tenant).where(Tenant.email == email))


def get_tenant_by_phone(phone: str) -> Tenant | None:
    """Retrieve a tenant by their phone number."""
    with SessionLocal() as session:
        return session.scalar(select(Tenant).where(Tenant.phone == phone))


def get_tenant_by_unit(unit_number: str) -> Tenant | None:
    """Retrieve a tenant based on their unit number."""
    with SessionLocal() as session:
        return session.scalar(select(Tenant).where(Tenant.unit_number == unit_number))


def answer_tenant_question(
    query: str,
    tenant_id: int | None = None,
    email: str | None = None,
    phone: str | None = None,
    unit_number: str | None = None,
) -> str:
    """
    Basic rule-based Q&A for tenant information.
    Attempts to locate a tenant based on provided identifiers and
    extracts requested information from the record.
    """
    tenant = None
    if tenant_id:
        tenant = get_tenant_by_id(tenant_id)
    elif email:
        tenant = get_tenant_by_email(email)
    elif phone:
        tenant = get_tenant_by_phone(phone)
    elif unit_number:
        tenant = get_tenant_by_unit(unit_number)

    if not tenant:
        return "Tenant not found."

    query_lower = query.lower()

    # Map keywords to tenant attributes
    attribute_map = {
        "name": f"Tenant name: {tenant.full_name}",
        "email": f"Email: {tenant.email}",
        "phone": f"Phone: {tenant.phone}",
        "unit": f"Unit: {tenant.unit_number}",
        "lease": f"Lease: {tenant.lease_start_date} to {tenant.lease_end_date}",
        "notes": f"Notes: {tenant.notes}",
    }

    for keyword, response in attribute_map.items():
        if keyword in query_lower:
            return response

    return f"Tenant info: {tenant.full_name}, Unit {tenant.unit_number}, Email: {tenant.email}"