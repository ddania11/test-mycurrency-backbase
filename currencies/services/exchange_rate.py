import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from currencies.models import Currency, CurrencyExchangeRate, Provider
from external.api_clients.adapters.base import ExchangeRateData

from .provider_manager import ProviderManager, get_provider_manager

logger = logging.getLogger(__name__)


@dataclass
class ConversionResult:
    """Result of a currency conversion."""

    source_currency: str
    exchanged_currency: str
    rate: Decimal
    source_amount: Decimal
    exchanged_amount: Decimal
    valuation_date: date


@dataclass
class RateTimeSeriesItem:
    """A single item in a rate time series."""

    date: date
    currency: str
    rate: Decimal


class ExchangeRateService:
    """
    Service for exchange rate operations.

    This service implements the business logic for:
    - Getting exchange rates (from DB or providers)
    - Converting amounts between currencies
    - Getting time series data for a date range

    The service follows a "database first" approach:
    1. Check if data exists in the database
    2. If not, fetch from external providers
    3. Store fetched data in the database
    4. Return the data
    """

    BASE_CURRENCY = "USD"

    def __init__(self, provider_manager: ProviderManager | None = None):
        """
        Initialize the service.

        Args:
            provider_manager: Optional ProviderManager instance.
                             If not provided, uses the global instance.
        """
        self._provider_manager = provider_manager or get_provider_manager()

    def get_exchange_rate(
        self,
        source_currency: str,
        exchanged_currency: str,
        valuation_date: date,
        provider: str | None = None,
    ) -> ExchangeRateData:
        """
        Get exchange rate between two currencies.

        First checks the database for existing data. If not found,
        fetches from external providers and stores the result.

        Args:
            source_currency: Source currency code
            exchanged_currency: Target currency code
            valuation_date: Date for the rate
            provider: Optional specific provider to use

        Returns:
            ExchangeRateData with rate information
        """
        source_currency = source_currency.upper()
        exchanged_currency = exchanged_currency.upper()

        # Try to get from database first
        db_rate = CurrencyExchangeRate.objects.get_rate(
            source_currency=source_currency,
            exchanged_currency=exchanged_currency,
            valuation_date=valuation_date,
        )

        if db_rate is not None:
            logger.debug(
                f"Found rate in database: {source_currency}→{exchanged_currency}={db_rate}"
            )
            return ExchangeRateData(
                source_currency=source_currency,
                exchanged_currency=exchanged_currency,
                valuation_date=valuation_date,
                rate_value=db_rate,
            )

        # Not in database, fetch from provider
        logger.debug(
            f"Rate not in database, fetching from provider: "
            f"{source_currency}→{exchanged_currency}"
        )

        rate_data = self._provider_manager.get_exchange_rate_data(
            source_currency=source_currency,
            exchanged_currency=exchanged_currency,
            valuation_date=valuation_date,
            provider_name=provider,
        )

        if provider is None:
            provider = rate_data.provider_name

        provider = Provider.objects.get(name=provider)

        # Store in database for future use
        self._store_rate(rate_data, provider)

        return rate_data

    def convert_amount(
        self,
        source_currency: str,
        exchanged_currency: str,
        amount: Decimal | float | int,
        valuation_date: date | None = None,
    ) -> ConversionResult:
        """
        Convert an amount from one currency to another.

        Args:
            source_currency: Source currency code
            exchanged_currency: Target currency code
            amount: Amount to convert
            valuation_date: Date for the rate (defaults to today)

        Returns:
            ConversionResult with conversion details
        """
        if valuation_date is None:
            valuation_date = date.today()

        amount = Decimal(str(amount))

        rate_data = self.get_exchange_rate(
            source_currency=source_currency,
            exchanged_currency=exchanged_currency,
            valuation_date=valuation_date,
        )

        exchanged_amount = amount * rate_data.rate

        return ConversionResult(
            source_currency=source_currency.upper(),
            exchanged_currency=exchanged_currency.upper(),
            rate=rate_data.rate,
            source_amount=amount,
            exchanged_amount=exchanged_amount.quantize(Decimal("0.000001")),
            valuation_date=valuation_date,
        )

    def get_rates_for_period(
        self,
        source_currency: str,
        date_from: date,
        date_to: date,
    ) -> dict[date, dict[str, Decimal]]:
        """
        Get exchange rates for a currency over a date range.

        Returns rates for all target currencies for each date in the range.
        Only returns rates that exist in the database.

        Args:
            source_currency: Source currency code
            date_from: Start date (inclusive)
            date_to: End date (inclusive)

        Returns:
            Dict mapping dates to dicts of currency→rate
        """
        source_currency = source_currency.upper()

        # Get existing rates from database
        existing_rates = CurrencyExchangeRate.objects.get_rates_for_period(
            source_currency=source_currency,
            date_from=date_from,
            date_to=date_to,
        )

        # Organize by date
        result: dict[date, dict[str, Decimal]] = {}
        for rate in existing_rates:
            if rate.valuation_date not in result:
                result[rate.valuation_date] = {}
            result[rate.valuation_date][rate.exchanged_currency.code] = rate.rate_value

        return dict(sorted(result.items()))

    def _store_rate(self, rate_data: ExchangeRateData, provider: Provider) -> None:
        """
        Store an exchange rate in the database.

        Args:
            rate_data: ExchangeRateData to store
            provider: Provider name
        """
        try:
            source = Currency.objects.get_by_code(rate_data.source_currency)
            target = Currency.objects.get_by_code(rate_data.exchanged_currency)

            CurrencyExchangeRate.objects.store_rate(
                source_currency=source,
                exchanged_currency=target,
                valuation_date=rate_data.valuation_date,
                rate_value=rate_data.rate,
                provider=provider,
            )
        except Currency.DoesNotExist as e:
            logger.warning(f"Could not store rate, currency not found: {e}")


# Convenience function matching the required signature
def get_exchange_rate_data(
    source_currency: str,
    exchanged_currency: str,
    valuation_date: date | str,
    provider: str | None = None,
) -> ExchangeRateData:
    """
    Get exchange rate data using the Adapter Design Pattern.

    This function provides the interface specified in the requirements:
    - First checks the database for existing data
    - Falls back to external providers if not found
    - Implements resilient provider fallback

    Args:
        source_currency: The base currency code (e.g., 'USD')
        exchanged_currency: The target currency code (e.g., 'EUR')
        valuation_date: The date for the rate (date object or 'YYYY-MM-DD')
        provider: Optional specific provider to use

    Returns:
        ExchangeRateData with rate information
    """
    if isinstance(valuation_date, str):
        valuation_date = date.fromisoformat(valuation_date)

    service = ExchangeRateService()
    return service.get_exchange_rate(
        source_currency=source_currency,
        exchanged_currency=exchanged_currency,
        valuation_date=valuation_date,
        provider=provider,
    )
