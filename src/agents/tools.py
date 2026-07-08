from __future__ import annotations

from typing import Any
from langchain_core.tools import tool

from src.agents import tenant, payment_tracker, maintenance_handler, forecaster


@tool
def get_tenant_details(identifier: str, id_type: str = "email") -> str:
    """
    Retrieve detailed information about a tenant.
    id_type can be 'email', 'phone', 'unit', or 'id'.
    Use this when you need to know a tenant's name, lease dates, or contact info.
    """
    if id_type == "email":
        t = tenant.get_tenant_by_email(identifier)
    elif id_type == "phone":
        t = tenant.get_tenant_by_phone(identifier)
    elif id_type == "unit":
        t = tenant.get_tenant_by_unit(identifier)
    elif id_type == "id":
        try:
            t = tenant.get_tenant_by_id(int(identifier))
        except ValueError:
            return "Invalid Tenant ID provided."
    else:
        return "Invalid id_type. Please use 'email', 'phone', 'unit', or 'id'."

    if not t:
        return "Tenant not found."

    return f"Tenant: {t.full_name}, Unit: {t.unit_number}, Email: {t.email}, Phone: {t.phone}, Lease: {t.lease_start_date} to {t.lease_end_date}, Notes: {t.notes}"


@tool
def check_payment_status(tenant_id: int) -> str:
    """
    Get the financial summary for a tenant.
    Use this to see if a tenant is up to date with rent or has overdue payments.
    """
    summary = payment_tracker.get_tenant_payment_summary(tenant_id)
    return (
        f"Payment Summary for Tenant {tenant_id}:\n"
        f"- Total Paid: {summary['total_paid']}\n"
        f"- Total Owed: {summary['total_owed']}\n"
        f"- Overdue Payments: {summary['overdue_count']}\n"
        f"- Total Records: {summary['payment_count']}"
    )


@tool
def get_overdue_payment_overview() -> str:
    """
    Retrieve a portfolio-wide overdue rent summary.
    Use this for landlord or dashboard questions asking who is overdue and how much is owed overall.
    """
    summary = payment_tracker.get_portfolio_overdue_summary()
    overdue_payments = summary["payments"]

    lines = [
        "Portfolio Overdue Summary:",
        f"- Overdue Payments: {summary['overdue_count']}",
        f"- Total Owed: {summary['total_overdue']} {'/'.join(summary['currencies'])}",
    ]

    if overdue_payments:
        lines.append("- Overdue Accounts:")
        for payment in overdue_payments:
            due_date = payment["due_date"].date().isoformat() if payment["due_date"] else "unknown"
            reference = payment["reference"] or "no reference"
            lines.append(
                f"  - Tenant {payment['tenant_id']} / Property {payment['property_id']}: "
                f"{payment['amount']} {payment['currency']} due {due_date} "
                f"(Payment {payment['payment_id']}, Ref: {reference})"
            )
    else:
        lines.append("- Overdue Accounts: none")

    return "\n".join(lines)


@tool
def mark_rent_as_paid(payment_id: int) -> str:
    """
    Mark a specific payment record as 'paid'.
    Use this when a tenant provides proof of payment or the landlord confirms receipt.
    """
    payment = payment_tracker.mark_payment_as_paid(payment_id)
    if payment:
        return f"Payment {payment_id} has been successfully marked as paid."
    return "Payment record not found."


@tool
def log_maintenance_issue(tenant_id: int, property_id: int, title: str, description: str = "") -> str:
    """
    Log a new maintenance request for a tenant.
    Use this when a tenant reports a problem (e.g., 'leaking tap', 'broken window').
    """
    req = maintenance_handler.add_maintenance_request(
        tenant_id=tenant_id,
        property_id=property_id,
        issue_title=title,
        issue_description=description
    )
    return f"Maintenance request {req.id} created successfully: {title}."


@tool
def get_maintenance_overview() -> str:
    """
    Retrieve a high-level summary of all maintenance requests.
    Use this to see how many requests are open, in-progress, or urgent.
    """
    summary = maintenance_handler.get_maintenance_summary()
    return (
        f"Maintenance Overview:\n"
        f"- Total: {summary['total_requests']}\n"
        f"- Open: {summary['open_requests']}\n"
        f"- In Progress: {summary['in_progress_requests']}\n"
        f"- Resolved: {summary['resolved_requests']}\n"
        f"- Escalated: {summary['escalated_requests']}\n"
        f"- High Priority: {summary['high_priority_requests']}"
    )


@tool
def get_income_forecast(property_id: int | None = None, tenant_id: int | None = None) -> str:
    """
    Generate a rental income forecast.
    Use this to estimate expected income for the next few months.
    """
    return forecaster.summarize_income_forecast(property_id=property_id, tenant_id=tenant_id)