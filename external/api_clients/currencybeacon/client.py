from typing import Any

from django.conf import settings

from external.api_clients.client import APIClient

from .services import ConversionService, CurrenciesService, RatesService


class CurrencyBeaconClient(APIClient):
    base_url: str = getattr(settings, "CURRENCY_BEACON_API_URL", "")

    def __init__(
        self,
        api_key: str | None = None,
        timeout: int = 30,
        cache_enabled: bool = True,
    ) -> None:
        resolved_api_key = api_key or getattr(settings, "CURRENCY_BEACON_API_KEY", None)

        super().__init__(
            api_key=resolved_api_key,
            timeout=timeout,
            cache_enabled=cache_enabled,
            cache_prefix="currencybeacon",
        )

        self._rates = RatesService(self)
        self._conversion = ConversionService(self)
        self._currencies = CurrenciesService(self)

    @property
    def rates(self) -> RatesService:
        """
        Access the rates service.

        Provides methods for:
            - get_latest(): Get current exchange rates
            - get_historical(): Get rates for a specific date
            - get_timeseries(): Get rates for a date range

        Returns:
            RatesService instance
        """
        return self._rates

    @property
    def conversion(self) -> ConversionService:
        """
        Access the conversion service.

        Provides methods for:
            - convert(): Convert an amount between currencies

        Returns:
            ConversionService instance
        """
        return self._conversion

    @property
    def currencies(self) -> CurrenciesService:
        """
        Access the currencies service.

        Provides methods for:
            - list(): Get all available currencies
            - get_by_code(): Get a specific currency by code

        Returns:
            CurrenciesService instance
        """
        return self._currencies

    def _get_default_headers(self) -> dict[str, Any]:
        headers = super()._get_default_headers()
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
