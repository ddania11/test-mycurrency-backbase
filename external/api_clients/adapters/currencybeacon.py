from datetime import date
from decimal import Decimal

from django.conf import settings

from external.api_clients.currencybeacon import CurrencyBeaconClient

from .base import CurrencyAdapter, ExchangeRateData


class CurrencyBeaconAdapter(CurrencyAdapter):
    """
    Adapter for the CurrencyBeacon API.

    Translates the CurrencyBeacon-specific API responses into
    the standardized ExchangeRateData format.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int | None = None,
    ):
        self._api_key = api_key or getattr(settings, "CURRENCY_BEACON_API_KEY", None)
        self._base_url = base_url
        self._timeout = timeout
        self._client: CurrencyBeaconClient | None = None

    @property
    def provider_name(self) -> str:
        return "currencybeacon"

    @property
    def client(self) -> CurrencyBeaconClient:
        if self._client is None:
            kwargs = {"api_key": self._api_key}
            if self._base_url:
                kwargs["base_url"] = self._base_url
            if self._timeout:
                kwargs["timeout"] = self._timeout
            self._client = CurrencyBeaconClient(**kwargs)
        return self._client

    def get_exchange_rate_data(
        self,
        source_currency: str,
        exchanged_currency: str,
        valuation_date: date | str,
    ) -> ExchangeRateData:
        """
        Get the exchange rate from CurrencyBeacon.

        For today's date, uses the /latest endpoint.
        For historical dates, uses the /historical endpoint.

        Args:
            source_currency: The base currency code (e.g., 'USD')
            exchanged_currency: The target currency code (e.g., 'EUR')
            valuation_date: The date for the exchange rate

        Returns:
            ExchangeRateData with standardized rate information

        Raises:
            ValueError: If the target currency rate is not found
            APIClientError: If there's an error fetching the data
        """
        normalized_date = self._normalize_date(valuation_date)

        # Choose the appropriate endpoint based on the date
        # Using the rates service from the client (composition pattern)
        if self._is_today(normalized_date):
            response = self.client.rates.get_latest(
                base=source_currency,
                symbols=[exchanged_currency],
            )
        else:
            response = self.client.rates.get_historical(
                valuation_date=normalized_date,
                base=source_currency,
                symbols=[exchanged_currency],
            )

        # Extract the rate for the target currency
        rate = response.rates.get(exchanged_currency)
        if rate is None:
            raise ValueError(
                f"Rate for {exchanged_currency} not found in response. "
                f"Available currencies: {list(response.rates.keys())}"
            )

        return ExchangeRateData(
            source_currency=source_currency.upper(),
            exchanged_currency=exchanged_currency.upper(),
            valuation_date=normalized_date,
            rate_value=Decimal(str(rate)),
            provider_name=self.provider_name,
        )
