from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import models
from django.db.models import QuerySet

if TYPE_CHECKING:
    from .models import Currency, CurrencyExchangeRate, Provider


class CurrencyManager(models.Manager["Currency"]):
    def get_active(self) -> QuerySet[Currency]:
        """Get all active currencies."""
        return self.filter(is_active=True)

    def get_by_code(self, code: str) -> Currency:
        """Get a currency by its code."""
        return self.get(code=code.upper())


class CurrencyExchangeRateManager(models.Manager["CurrencyExchangeRate"]):
    BASE_CURRENCY_CODE = "USD"

    def get_rate(
        self,
        source_currency: str,
        exchanged_currency: str,
        valuation_date: date,
    ) -> Decimal | None:
        """
        Get the exchange rate between two currencies for a specific date.

        First tries to find a direct rate. If not found, calculates
        a cross rate using the base currency (USD).

        Args:
            source_currency: Source currency code
            exchanged_currency: Target currency code
            valuation_date: The date for the rate

        Returns:
            The exchange rate as Decimal, or None if not found
        """
        if source_currency == exchanged_currency:
            return Decimal("1")

        direct_rate = self.filter(
            source_currency__code=source_currency,
            exchanged_currency__code=exchanged_currency,
            valuation_date=valuation_date,
        ).first()

        if direct_rate:
            return direct_rate.rate_value

        inverse_rate = self.filter(
            source_currency__code=exchanged_currency,
            exchanged_currency__code=source_currency,
            valuation_date=valuation_date,
        ).first()

        if inverse_rate:
            return Decimal("1") / inverse_rate.rate_value

        return self._calculate_cross_rate(
            source_currency, exchanged_currency, valuation_date
        )

    def _calculate_cross_rate(
        self,
        source_currency: str,
        exchanged_currency: str,
        valuation_date: date,
    ) -> Decimal | None:
        """
        Calculate cross rate using base currency (USD) as intermediary.

        EUR → CHF = (USD → CHF) / (USD → EUR)
        """
        base = self.BASE_CURRENCY_CODE

        if source_currency == base:
            rate = self.filter(
                source_currency__code=base,
                exchanged_currency__code=exchanged_currency,
                valuation_date=valuation_date,
            ).first()
            return rate.rate_value if rate else None

        if exchanged_currency == base:
            rate = self.filter(
                source_currency__code=base,
                exchanged_currency__code=source_currency,
                valuation_date=valuation_date,
            ).first()
            return Decimal("1") / rate.rate_value if rate else None

        source_to_base = self.filter(
            source_currency__code=base,
            exchanged_currency__code=source_currency,
            valuation_date=valuation_date,
        ).first()

        target_to_base = self.filter(
            source_currency__code=base,
            exchanged_currency__code=exchanged_currency,
            valuation_date=valuation_date,
        ).first()

        if source_to_base and target_to_base:
            return target_to_base.rate_value / source_to_base.rate_value

        return None

    def get_rates_for_period(
        self,
        source_currency: str,
        date_from: date,
        date_to: date,
    ) -> QuerySet[CurrencyExchangeRate]:
        """
        Get all exchange rates for a source currency within a date range.

        Args:
            source_currency: Source currency code
            date_from: Start date (inclusive)
            date_to: End date (inclusive)

        Returns:
            QuerySet of CurrencyExchangeRate objects
        """
        return (
            self.filter(
                source_currency__code=source_currency,
                valuation_date__range=(date_from, date_to),
            )
            .select_related("source_currency", "exchanged_currency")
            .order_by("valuation_date", "exchanged_currency__code")
        )

    def get_missing_dates(
        self,
        source_currency: str,
        date_from: date,
        date_to: date,
    ) -> list[date]:
        """
        Find dates within a range that don't have exchange rate data.

        Args:
            source_currency: Source currency code
            date_from: Start date
            date_to: End date

        Returns:
            List of dates without rate data
        """
        from datetime import timedelta

        existing_dates = set(
            self.filter(
                source_currency__code=source_currency,
                valuation_date__range=(date_from, date_to),
            ).values_list("valuation_date", flat=True)
        )

        all_dates = []
        current = date_from
        while current <= date_to:
            all_dates.append(current)
            current += timedelta(days=1)

        return [d for d in all_dates if d not in existing_dates]

    def get_timeseries(
        self,
        source_currency: str,
        exchanged_currency: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict]:
        """
        Get time series data. Tries direct pair first, then inverse.
        """
        # 1. Try direct pair
        qs = self.filter(
            source_currency__code=source_currency,
            exchanged_currency__code=exchanged_currency,
        ).order_by("valuation_date")

        if date_from:
            qs = qs.filter(valuation_date__gte=date_from)
        if date_to:
            qs = qs.filter(valuation_date__lte=date_to)

        data = list(qs.values("valuation_date", "rate_value"))

        if data:
            return data

        # 2. Try inverse pair
        qs_inv = self.filter(
            source_currency__code=exchanged_currency,
            exchanged_currency__code=source_currency,
        ).order_by("valuation_date")

        if date_from:
            qs_inv = qs_inv.filter(valuation_date__gte=date_from)
        if date_to:
            qs_inv = qs_inv.filter(valuation_date__lte=date_to)

        data_inv = list(qs_inv.values("valuation_date", "rate_value"))

        if data_inv:
            return [
                {
                    "valuation_date": item["valuation_date"],
                    "rate_value": Decimal("1") / item["rate_value"],
                }
                for item in data_inv
            ]

        return []

    def store_rate(
        self,
        source_currency: Currency,
        exchanged_currency: Currency,
        valuation_date: date,
        rate_value: Decimal,
        provider: Provider,
    ) -> tuple[CurrencyExchangeRate, bool]:
        """
        Store an exchange rate, avoiding duplicates.

        Args:
            source_currency: Source Currency instance
            exchanged_currency: Target Currency instance
            valuation_date: Date of the rate
            rate_value: The exchange rate value
            provider: Name of the provider that supplied the rate

        Returns:
            Tuple of (CurrencyExchangeRate, created)
        """
        return self.get_or_create(
            source_currency=source_currency,
            exchanged_currency=exchanged_currency,
            valuation_date=valuation_date,
            defaults={
                "rate_value": rate_value,
                "provider": provider,
            },
        )


class ProviderManager(models.Manager["Provider"]):
    """Custom manager for Provider model."""

    def get_active_ordered(self) -> QuerySet[Provider]:
        """Get active providers ordered by priority."""
        return self.filter(is_active=True).order_by("priority")

    def get_default(self) -> Provider | None:
        """Get the highest priority active provider."""
        return self.get_active_ordered().first()
