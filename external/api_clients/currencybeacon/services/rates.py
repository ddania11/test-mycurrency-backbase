from datetime import date

from external.api_clients.currencybeacon.schemas import (
    ExchangeRateResponse,
    TimeSeriesResponse,
)

from .base import BaseService


class RatesService(BaseService):
    """
    Service for exchange rate operations.

    Provides methods to fetch current, historical, and time series
    exchange rate data from the CurrencyBeacon API.

    """

    # Cache TTL constants (in seconds)
    LATEST_CACHE_TTL = 3600  # 1 hour - rates change frequently
    HISTORICAL_CACHE_TTL = 86400  # 24 hours - historical data is immutable
    TIMESERIES_CACHE_TTL = 86400  # 24 hours

    def get_latest(
        self,
        base: str = "USD",
        symbols: list[str] | None = None,
    ) -> ExchangeRateResponse:
        """
        Get the latest exchange rates.

        Args:
            base: Base currency code (e.g., 'USD', 'EUR')
            symbols: Optional list of target currency codes to filter.
                    If None, returns rates for all available currencies.

        Returns:
            ExchangeRateResponse containing the base currency, date,
            and a dictionary of currency codes to rates.
        """
        params: dict[str, str] = {"base": base}
        if symbols:
            params["symbols"] = ",".join(symbols)

        response = self._client.get(
            "/latest",
            params=params,
            cache=True,
            cache_ttl=self.LATEST_CACHE_TTL,
        )
        return self._parse_response(response, ExchangeRateResponse)

    def get_historical(
        self,
        valuation_date: date | str,
        base: str = "USD",
        symbols: list[str] | None = None,
    ) -> ExchangeRateResponse:
        """
        Get historical exchange rates for a specific date.

        Args:
            valuation_date: The date for which to retrieve rates.
                           Accepts date object or ISO format string (YYYY-MM-DD).
            base: Base currency code (e.g., 'USD', 'EUR')
            symbols: Optional list of target currency codes to filter.

        Returns:
            ExchangeRateResponse containing the historical rates.

        Note:
            Historical data is cached for 24 hours since it never changes.
        """
        date_str = (
            valuation_date.isoformat()
            if isinstance(valuation_date, date)
            else valuation_date
        )

        params: dict[str, str] = {"base": base, "date": date_str}
        if symbols:
            params["symbols"] = ",".join(symbols)

        response = self._client.get(
            "/historical",
            params=params,
            cache=True,
            cache_ttl=self.HISTORICAL_CACHE_TTL,
        )
        return self._parse_response(response, ExchangeRateResponse)

    def get_timeseries(
        self,
        start_date: date | str,
        end_date: date | str,
        base: str = "USD",
        symbols: list[str] | None = None,
    ) -> TimeSeriesResponse:
        """
        Get exchange rates for a date range.

        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).
            base: Base currency code (e.g., 'USD', 'EUR')
            symbols: Optional list of target currency codes to filter.

        Returns:
            TimeSeriesResponse containing rates for each date in the range.
            The rates dict is keyed by date string, with each value being
            a dict of currency codes to rates.
        """
        start_str = (
            start_date.isoformat() if isinstance(start_date, date) else start_date
        )
        end_str = end_date.isoformat() if isinstance(end_date, date) else end_date

        params: dict[str, str] = {
            "base": base,
            "start_date": start_str,
            "end_date": end_str,
        }
        if symbols:
            params["symbols"] = ",".join(symbols)

        response = self._client.get(
            "/timeseries",
            params=params,
            cache=True,
            cache_ttl=self.TIMESERIES_CACHE_TTL,
        )
        return self._parse_response(response, TimeSeriesResponse)
