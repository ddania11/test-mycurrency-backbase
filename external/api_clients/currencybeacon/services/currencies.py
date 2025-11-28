from external.api_clients.currencybeacon.schemas import CurrenciesResponse, CurrencyInfo

from .base import BaseService


class CurrenciesService(BaseService):
    # Cache TTL constants (in seconds)
    CURRENCIES_CACHE_TTL = 604800  # 1 week - currency list rarely changes

    def list(self, currency_type: str = "fiat") -> list[CurrencyInfo]:
        """
        Get a list of all available currencies.

        Args:
            currency_type: Type of currencies to retrieve.
                          Options: "fiat" (default) or "crypto"

        Returns:
            List of CurrencyInfo objects containing:
                - id: Unique identifier
                - code: Currency code (e.g., 'USD')
                - name: Full currency name (e.g., 'United States Dollar')
                - symbol: Currency symbol (e.g., '$')
                - And other metadata

        Note:
            Results are cached for 1 week since the list of
            supported currencies rarely changes.
        """
        response = self._client.get(
            "/currencies",
            params={"type": currency_type},
            cache=True,
            cache_ttl=self.CURRENCIES_CACHE_TTL,
        )
        parsed = self._parse_response(response, CurrenciesResponse)
        return parsed.response

    def get_by_code(
        self, code: str, currency_type: str = "fiat"
    ) -> CurrencyInfo | None:
        """
        Get a specific currency by its code.

        Args:
            code: The currency code to look up (e.g., 'USD', 'EUR')
            currency_type: Type of currency ("fiat" or "crypto")

        Returns:
            CurrencyInfo if found, None otherwise
        """
        currencies = self.list(currency_type=currency_type)
        code_upper = code.upper()
        return next(
            (c for c in currencies if c.short_code.upper() == code_upper),
            None,
        )
