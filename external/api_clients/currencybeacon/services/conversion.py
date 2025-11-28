from external.api_clients.currencybeacon.schemas import ConvertResponse

from .base import BaseService


class ConversionService(BaseService):
    CONVERT_CACHE_TTL = 3600

    def convert(
        self,
        from_currency: str,
        to_currency: str,
        amount: float,
    ) -> ConvertResponse:
        """
        Convert an amount from one currency to another.

        Uses real-time exchange rates to perform the conversion.
        Results are cached for 1 hour to reduce API calls.

        Args:
            from_currency: Source currency code (e.g., 'USD')
            to_currency: Target currency code (e.g., 'EUR')
            amount: The amount to convert

        Returns:
            ConvertResponse containing:
                - from_currency: The source currency
                - to: The target currency
                - amount: The original amount
                - value: The converted amount
                - date: The date of the exchange rate used
        """
        params = {
            "from": from_currency,
            "to": to_currency,
            "amount": amount,
        }

        response = self._client.get(
            "/convert",
            params=params,
            cache=True,
            cache_ttl=self.CONVERT_CACHE_TTL,
        )
        return self._parse_response(response, ConvertResponse)
