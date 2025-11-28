from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field

CurrencyCode = Annotated[
    str,
    BeforeValidator(lambda v: v.upper() if isinstance(v, str) else v),
    Field(min_length=3, max_length=3),
]


class ExchangeRateData(BaseModel):
    """
    Standardized exchange rate data returned by all adapters.

    This is the common response format that the rest of the application
    will receive, regardless of which provider was used.

    Attributes:
        source_currency: The base currency code (e.g., 'USD')
        exchanged_currency: The target currency code (e.g., 'EUR')
        valuation_date: The date for which the rate applies
        rate_value: The exchange rate as a Decimal
        provider_name: The name of the provider that supplied the data
    """

    model_config = {"frozen": True}

    source_currency: CurrencyCode
    exchanged_currency: CurrencyCode
    valuation_date: date
    rate_value: Decimal = Field(..., gt=0)
    provider_name: str | None = None

    @property
    def rate(self) -> Decimal:
        """Alias for rate_value (backward compatibility)."""
        return self.rate_value


class CurrencyAdapter(ABC):
    """
    Abstract base class for currency exchange rate adapters.

    All currency data providers must implement this interface,
    ensuring the rest of the application remains decoupled from
    the specific provider implementations.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    def get_exchange_rate_data(
        self,
        source_currency: str,
        exchanged_currency: str,
        valuation_date: date | str,
    ) -> ExchangeRateData:
        pass

    def _normalize_date(self, valuation_date: date | str) -> date:
        if isinstance(valuation_date, str):
            return date.fromisoformat(valuation_date)
        return valuation_date

    def _is_today(self, valuation_date: date) -> bool:
        return valuation_date == date.today()
