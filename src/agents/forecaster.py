from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select

from src.database import SessionLocal
from src.models import Payment


_TWOPLACES = Decimal("0.01")
_ZERO = Decimal("0.00")


@dataclass(frozen=True)
class MonthlyIncomeSnapshot:
    month: str
    expected_income: Decimal
    collected_income: Decimal
    collection_rate: float


@dataclass(frozen=True)
class ForecastMonth:
    month: str
    baseline_income: Decimal
    projected_income: Decimal
    projected_collection_rate: float
    confidence: float


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(_TWOPLACES, rounding=ROUND_HALF_UP)


def _to_decimal(value: Decimal | int | float | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _month_anchor(value: datetime) -> date:
    return date(value.year, value.month, 1)


def _add_months(month: date, offset: int) -> date:
    month_index = month.month - 1 + offset
    return date(month.year + month_index // 12, month_index % 12 + 1, 1)


def _format_month(month: date) -> str:
    return month.strftime("%Y-%m")


def _mean(values: Iterable[Decimal]) -> Decimal:
    values = list(values)
    if not values:
        return _ZERO
    return sum(values, start=_ZERO) / Decimal(len(values))


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def build_monthly_income_history(
        payments: Iterable[Payment],
        trailing_months: int = 6,
        as_of: datetime | None = None,
) -> list[MonthlyIncomeSnapshot]:
    if trailing_months < 1:
        raise ValueError("trailing_months must be at least 1")

    as_of = _normalize_datetime(as_of) or datetime.now(timezone.utc)
    current_month = _month_anchor(as_of)

    months = [
        _add_months(current_month, -(trailing_months - 1) + index)
        for index in range(trailing_months)
    ]
    month_set = set(months)

    expected_by_month: dict[date, Decimal] = defaultdict(lambda: _ZERO)
    collected_by_month: dict[date, Decimal] = defaultdict(lambda: _ZERO)

    for payment in payments:
        amount = _to_decimal(payment.amount)

        due_date = _normalize_datetime(payment.due_date)
        created_at = _normalize_datetime(getattr(payment, "created_at", None))
        paid_at = _normalize_datetime(payment.paid_at)

        expected_reference = due_date or created_at
        if expected_reference is not None:
            expected_month = _month_anchor(expected_reference)
            if expected_month in month_set:
                expected_by_month[expected_month] += amount

        if payment.status == "paid":
            collected_reference = paid_at or due_date or created_at
            if collected_reference is not None:
                collected_month = _month_anchor(collected_reference)
                if collected_month in month_set:
                    collected_by_month[collected_month] += amount

    history: list[MonthlyIncomeSnapshot] = []

    for month in months:
        expected_income = _quantize(expected_by_month[month])
        collected_income = _quantize(collected_by_month[month])

        collection_rate = 0.0
        if expected_income > 0:
            collection_rate = round(float(collected_income / expected_income), 2)

        history.append(
            MonthlyIncomeSnapshot(
                month=_format_month(month),
                expected_income=expected_income,
                collected_income=collected_income,
                collection_rate=collection_rate,
            )
        )

    return history


def _confidence_score(history: list[MonthlyIncomeSnapshot]) -> float:
    active_months = [item for item in history if item.expected_income > 0]

    if not active_months:
        return 0.35

    expected_values = [item.expected_income for item in active_months]
    average_expected = _mean(expected_values)

    if average_expected == 0:
        return 0.35

    average_deviation = _mean(abs(value - average_expected) for value in expected_values)
    volatility = float(average_deviation / average_expected)
    coverage = len(active_months) / max(len(history), 1)

    confidence = 0.55 + (0.25 * coverage) - (0.20 * min(volatility, 1.0))
    return round(_clamp(confidence, 0.35, 0.95), 2)


def list_payments_for_forecast(
        property_id: int | None = None,
        tenant_id: int | None = None,
) -> list[Payment]:
    query = select(Payment).order_by(Payment.due_date, Payment.created_at)

    if property_id is not None:
        query = query.where(Payment.property_id == property_id)

    if tenant_id is not None:
        query = query.where(Payment.tenant_id == tenant_id)

    with SessionLocal() as session:
        return session.scalars(query).all()


def forecast_income(
        payments: Iterable[Payment],
        months_ahead: int = 3,
        lookback_months: int = 6,
        as_of: datetime | None = None,
) -> list[ForecastMonth]:
    if months_ahead < 1:
        raise ValueError("months_ahead must be at least 1")

    if lookback_months < 1:
        raise ValueError("lookback_months must be at least 1")

    as_of = _normalize_datetime(as_of) or datetime.now(timezone.utc)

    history = build_monthly_income_history(
        payments,
        trailing_months=lookback_months,
        as_of=as_of,
    )

    expected_values = [item.expected_income for item in history]
    collected_values = [item.collected_income for item in history]

    average_expected = _mean(expected_values)

    monthly_collection_rates = [
        Decimal(str(item.collection_rate))
        for item in history
    ]

    raw_projected_collection_rate = _ZERO
    if monthly_collection_rates:
        raw_projected_collection_rate = (
                sum(monthly_collection_rates, start=_ZERO)
                / Decimal(len(monthly_collection_rates))
        )

    projected_collection_rate = round(
        _clamp(float(raw_projected_collection_rate), 0.0, 1.0),
        2,
    )

    non_zero_expected = [value for value in expected_values if value > 0]

    monthly_trend = _ZERO
    if len(non_zero_expected) >= 2:
        monthly_trend = (
                                non_zero_expected[-1] - non_zero_expected[0]
                        ) / Decimal(len(non_zero_expected) - 1)

    confidence = _confidence_score(history)
    anchor_month = _month_anchor(as_of)

    forecasts: list[ForecastMonth] = []

    for step in range(1, months_ahead + 1):
        baseline_income = average_expected + (monthly_trend * Decimal(step))

        if baseline_income < 0:
            baseline_income = _ZERO

        projected_income = baseline_income * raw_projected_collection_rate

        forecasts.append(
            ForecastMonth(
                month=_format_month(_add_months(anchor_month, step)),
                baseline_income=_quantize(baseline_income),
                projected_income=_quantize(projected_income),
                projected_collection_rate=projected_collection_rate,
                confidence=confidence,
            )
        )

    return forecasts


def generate_income_forecast(
        property_id: int | None = None,
        tenant_id: int | None = None,
        months_ahead: int = 3,
        lookback_months: int = 6,
        as_of: datetime | None = None,
) -> dict[str, list[MonthlyIncomeSnapshot] | list[ForecastMonth]]:
    payments = list_payments_for_forecast(
        property_id=property_id,
        tenant_id=tenant_id,
    )

    return {
        "history": build_monthly_income_history(
            payments,
            trailing_months=lookback_months,
            as_of=as_of,
        ),
        "forecast": forecast_income(
            payments,
            months_ahead=months_ahead,
            lookback_months=lookback_months,
            as_of=as_of,
        ),
    }


def summarize_income_forecast(
        property_id: int | None = None,
        tenant_id: int | None = None,
        months_ahead: int = 3,
        lookback_months: int = 6,
        as_of: datetime | None = None,
) -> str:
    result = generate_income_forecast(
        property_id=property_id,
        tenant_id=tenant_id,
        months_ahead=months_ahead,
        lookback_months=lookback_months,
        as_of=as_of,
    )

    forecast = result["forecast"]

    if not forecast:
        return "Not enough payment history to generate an income forecast."

    next_month = forecast[0]

    return (
        f"Projected rental income for {next_month.month} is "
        f"{next_month.projected_income:,.2f} with a baseline of "
        f"{next_month.baseline_income:,.2f}, a projected collection rate of "
        f"{next_month.projected_collection_rate:.0%}, and confidence "
        f"{next_month.confidence:.0%}."
    )