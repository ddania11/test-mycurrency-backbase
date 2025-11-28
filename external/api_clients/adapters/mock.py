import random
from datetime import date
from decimal import Decimal

from .base import CurrencyAdapter, ExchangeRateData


class MockAdapter(CurrencyAdapter):
    """
    Mock adapter that generates random exchange rates.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int | None = None,
    ):
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout

    @property
    def provider_name(self) -> str:
        return "mock"

    def get_exchange_rate_data(
        self,
        source_currency: str,
        exchanged_currency: str,
        valuation_date: date | str,
    ) -> ExchangeRateData:
        """
        Generate a random exchange rate for the given pair.
        """
        if isinstance(valuation_date, str):
            valuation_date = date.fromisoformat(valuation_date)

        # Generate random rate between 0.5 and 1.5
        random_rate = random.uniform(0.5, 1.5)
        rate_value = Decimal(f"{random_rate:.6f}")

        return ExchangeRateData(
            source_currency=source_currency.upper(),
            exchanged_currency=exchanged_currency.upper(),
            valuation_date=valuation_date,
            rate_value=rate_value,
            provider_name=self.provider_name,
        )
