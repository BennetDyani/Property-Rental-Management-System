from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from src.agents import payment_agent, payment_tracker
from src.agents.forecaster import build_monthly_income_history, forecast_income
from src.models import Payment


def make_payment(
    *,
    amount: str,
    status: str,
    due_date: datetime,
    paid_at: datetime | None = None,
) -> Payment:
    return Payment(
        tenant_id=1,
        property_id=1,
        amount=Decimal(amount),
        status=status,
        currency="ZAR",
        due_date=due_date,
        paid_at=paid_at,
        reference=f"test-{amount}-{due_date.isoformat()}",
    )


def test_build_monthly_income_history_groups_expected_and_collected_income():
    payments = [
        make_payment(
            amount="1000.00",
            status="paid",
            due_date=datetime(2026, 1, 5, tzinfo=timezone.utc),
            paid_at=datetime(2026, 1, 6, tzinfo=timezone.utc),
        ),
        make_payment(
            amount="1500.00",
            status="paid",
            due_date=datetime(2026, 2, 5, tzinfo=timezone.utc),
            paid_at=datetime(2026, 2, 9, tzinfo=timezone.utc),
        ),
        make_payment(
            amount="2000.00",
            status="pending",
            due_date=datetime(2026, 3, 5, tzinfo=timezone.utc),
        ),
    ]

    history = build_monthly_income_history(
        payments,
        trailing_months=3,
        as_of=datetime(2026, 3, 31, tzinfo=timezone.utc),
    )

    assert [item.month for item in history] == ["2026-01", "2026-02", "2026-03"]
    assert history[0].expected_income == Decimal("1000.00")
    assert history[0].collected_income == Decimal("1000.00")
    assert history[0].collection_rate == 1.0
    assert history[2].expected_income == Decimal("2000.00")
    assert history[2].collected_income == Decimal("0.00")
    assert history[2].collection_rate == 0.0


def test_forecast_income_projects_future_months_from_history():
    payments = [
        make_payment(
            amount="1000.00",
            status="paid",
            due_date=datetime(2026, 1, 5, tzinfo=timezone.utc),
            paid_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
        ),
        make_payment(
            amount="1200.00",
            status="paid",
            due_date=datetime(2026, 2, 5, tzinfo=timezone.utc),
            paid_at=datetime(2026, 2, 7, tzinfo=timezone.utc),
        ),
        make_payment(
            amount="1400.00",
            status="pending",
            due_date=datetime(2026, 3, 5, tzinfo=timezone.utc),
        ),
    ]

    forecast = forecast_income(
        payments,
        months_ahead=2,
        lookback_months=3,
        as_of=datetime(2026, 3, 31, tzinfo=timezone.utc),
    )

    assert [item.month for item in forecast] == ["2026-04", "2026-05"]
    assert forecast[0].baseline_income == Decimal("1400.00")
    assert forecast[0].projected_income == Decimal("933.33")
    assert forecast[0].projected_collection_rate == 0.67
    assert forecast[1].baseline_income == Decimal("1600.00")
    assert forecast[1].projected_income == Decimal("1066.67")


def test_get_portfolio_overdue_summary_aggregates_overdue_balances(monkeypatch):
    overdue_payments = [
        make_payment(
            amount="1000.00",
            status="pending",
            due_date=datetime(2026, 7, 1, tzinfo=timezone.utc),
        ),
        make_payment(
            amount="1500.00",
            status="overdue",
            due_date=datetime(2026, 7, 5, tzinfo=timezone.utc),
        ),
    ]
    overdue_payments[0].id = 1
    overdue_payments[0].tenant_id = 3
    overdue_payments[0].property_id = 10
    overdue_payments[0].reference = "JHB-1001"
    overdue_payments[1].id = 2
    overdue_payments[1].tenant_id = 4
    overdue_payments[1].property_id = 11
    overdue_payments[1].reference = "CPT-2002"

    monkeypatch.setattr(payment_tracker, "get_overdue_payments", lambda: overdue_payments)

    summary = payment_tracker.get_portfolio_overdue_summary()

    assert summary["overdue_count"] == 2
    assert summary["total_overdue"] == Decimal("2500.00")
    assert summary["currencies"] == ["ZAR"]
    assert summary["payments"][0]["tenant_id"] == 3
    assert summary["payments"][1]["reference"] == "CPT-2002"


def test_payment_agent_returns_portfolio_overdue_summary_without_llm(monkeypatch):
    class DummyRetriever:
        def search(self, query: str):
            raise AssertionError("search should not be called for portfolio overdue summaries")

    monkeypatch.setattr(payment_agent, "ChatGroq", lambda *args, **kwargs: object())
    monkeypatch.setattr(payment_agent, "create_react_agent", lambda *args, **kwargs: object())
    monkeypatch.setattr(
        payment_agent,
        "get_overdue_payment_overview",
        SimpleNamespace(invoke=lambda payload: "Portfolio Overdue Summary"),
    )

    agent = payment_agent.PaymentAgent(retriever=DummyRetriever())

    response = agent.process_query("Who is currently overdue on rent and how much is owed?", tenant_id=None)

    assert response == "Portfolio Overdue Summary"