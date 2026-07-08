from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from src.database import SessionLocal
from src.models import Maintenance


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def add_maintenance_request(
    tenant_id: int,
    property_id: int,
    issue_title: str,
    issue_description: str | None = None,
    status: str = "open",
    priority: str = "medium",
    notes: str | None = None,
) -> Maintenance:
    """Log a new maintenance request in the system."""
    request = Maintenance(
        tenant_id=tenant_id,
        property_id=property_id,
        issue_title=issue_title,
        issue_description=issue_description,
        status=status,
        priority=priority,
        notes=notes,
    )

    with SessionLocal() as session:
        session.add(request)
        session.commit()
        session.refresh(request)

    return request


def get_request_by_id(request_id: int) -> Maintenance | None:
    """Retrieve a specific maintenance request by its ID."""
    with SessionLocal() as session:
        return session.get(Maintenance, request_id)


def list_maintenance_requests(
    status: str | None = None,
    priority: str | None = None,
    tenant_id: int | None = None,
) -> list[Maintenance]:
    """Retrieve maintenance requests with optional filtering."""
    query = select(Maintenance)

    if status:
        query = query.where(Maintenance.status == status)
    if priority:
        query = query.where(Maintenance.priority == priority)
    if tenant_id:
        query = query.where(Maintenance.tenant_id == tenant_id)

    with SessionLocal() as session:
        return session.scalars(query.order_by(Maintenance.created_at.desc())).all()


def schedule_request(
    request_id: int,
    scheduled_for: datetime,
    notes: str | None = None,
) -> Maintenance | None:
    """Set a date for the repair visit and mark as 'scheduled'."""
    with SessionLocal() as session:
        request = session.get(Maintenance, request_id)
        if not request:
            return None

        request.scheduled_for = _normalize_datetime(scheduled_for)
        request.status = "scheduled"

        if notes:
            request.notes = f"{request.notes}\n{notes}".strip() if request.notes else notes

        session.commit()
        session.refresh(request)
        return request


def mark_in_progress(request_id: int, notes: str | None = None) -> Maintenance | None:
    """Mark a request as being actively worked on."""
    with SessionLocal() as session:
        request = session.get(Maintenance, request_id)
        if not request:
            return None

        request.status = "in_progress"
        if notes:
            request.notes = f"{request.notes}\n{notes}".strip() if request.notes else notes

        session.commit()
        session.refresh(request)
        return request


def resolve_request(request_id: int, resolution_notes: str | None = None) -> Maintenance | None:
    """Mark a request as resolved and record the completion time."""
    with SessionLocal() as session:
        request = session.get(Maintenance, request_id)
        if not request:
            return None

        request.status = "resolved"
        request.resolved_at = datetime.now(timezone.utc)

        if resolution_notes:
            request.notes = (
                f"{request.notes}\nResolved: {resolution_notes}".strip()
                if request.notes
                else f"Resolved: {resolution_notes}"
            )

        session.commit()
        session.refresh(request)
        return request


def escalate_old_open_requests(days_open: int = 7) -> list[Maintenance]:
    """
    Find requests that have been 'open' or 'in_progress' for longer than
    the specified days and mark them as 'escalated'.
    """
    threshold_date = datetime.now(timezone.utc) - timedelta(days=days_open)

    with SessionLocal() as session:
        # Only escalate requests that are not yet resolved or scheduled
        query = select(Maintenance).where(
            Maintenance.status.in_(["open", "in_progress"]),
            Maintenance.created_at <= threshold_date,
        )
        requests = session.scalars(query).all()

        escalated = []
        for req in requests:
            req.status = "escalated"
            escalated.append(req)

        session.commit()
        return escalated


def get_maintenance_summary() -> dict[str, int]:
    """Generate an overview of all maintenance requests by status and priority."""
    all_requests = list_maintenance_requests()

    return {
        "total_requests": len(all_requests),
        "open_requests": sum(1 for r in all_requests if r.status == "open"),
        "in_progress_requests": sum(1 for r in all_requests if r.status == "in_progress"),
        "scheduled_requests": sum(1 for r in all_requests if r.status == "scheduled"),
        "resolved_requests": sum(1 for r in all_requests if r.status == "resolved"),
        "escalated_requests": sum(1 for r in all_requests if r.status == "escalated"),
        "high_priority_requests": sum(1 for r in all_requests if r.priority in ["high", "urgent"]),
    }