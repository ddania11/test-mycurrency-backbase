from datetime import date
from typing import TYPE_CHECKING

from .base import CurrencyAdapter, ExchangeRateData
from .currencybeacon import CurrencyBeaconAdapter
from .mock import MockAdapter

if TYPE_CHECKING:
    from currencies.models import Provider

# Registry of available adapters (maps provider name to adapter class)
ADAPTERS: dict[str, type[CurrencyAdapter]] = {
    "currencybeacon": CurrencyBeaconAdapter,
    "mock": MockAdapter,
}

# Default provider if none specified
DEFAULT_PROVIDER = "currencybeacon"


def get_adapter(provider: str | None = None) -> CurrencyAdapter:
    """
    Get an adapter instance for the specified provider.

    Args:
        provider: The provider name (e.g., 'currencybeacon', 'fixer').
                  If None, uses the default provider.

    Returns:
        An instance of the appropriate CurrencyAdapter

    Raises:
        ValueError: If the provider is not supported
    """
    provider = provider or DEFAULT_PROVIDER
    provider = provider.lower()

    adapter_class = ADAPTERS.get(provider)
    if adapter_class is None:
        available = ", ".join(ADAPTERS.keys())
        raise ValueError(
            f"Unknown provider: '{provider}'. Available providers: {available}"
        )

    return adapter_class()


def get_adapter_for_provider(provider: "Provider") -> CurrencyAdapter:
    """
    Get an adapter instance configured with a Provider model instance.

    This allows using database-stored configuration (API key, URL, timeout)
    for the adapter instead of environment variables.

    Args:
        provider: A Provider model instance with configuration

    Returns:
        An instance of the appropriate CurrencyAdapter configured
        with the provider's settings

    Raises:
        ValueError: If the provider type is not supported
    """
    adapter_class = ADAPTERS.get(provider.name.lower())
    if adapter_class is None:
        available = ", ".join(ADAPTERS.keys())
        raise ValueError(
            f"Unknown provider: '{provider.name}'. Available providers: {available}"
        )

    # Create adapter with provider configuration
    return adapter_class(
        api_key=provider.api_key,
        base_url=provider.api_url,
        timeout=provider.timeout_seconds,
    )


def register_adapter(name: str, adapter_class: type[CurrencyAdapter]) -> None:
    """
    Register a new adapter in the registry.

    Allows dynamic registration of new providers at runtime.

    Args:
        name: The provider name (will be lowercased)
        adapter_class: The adapter class (must inherit from CurrencyAdapter)
    """
    if not issubclass(adapter_class, CurrencyAdapter):
        raise TypeError(
            f"adapter_class must be a subclass of CurrencyAdapter, "
            f"got {type(adapter_class)}"
        )
    ADAPTERS[name.lower()] = adapter_class


def get_exchange_rate_data(
    source_currency: str,
    exchanged_currency: str,
    valuation_date: date | str,
    provider: str | None = None,
) -> ExchangeRateData:
    """
    Get exchange rate data using the Adapter Design Pattern.

    This is the main entry point for the rest of the application.
    It abstracts away the specific provider implementation, returning
    standardized ExchangeRateData regardless of which provider is used.

    Args:
        source_currency: The base currency code (e.g., 'USD')
        exchanged_currency: The target currency code (e.g., 'EUR')
        valuation_date: The date for the exchange rate (date object or 'YYYY-MM-DD' string)
        provider: The provider to use (e.g., 'currencybeacon').
                  If None, uses the default provider.

    Returns:
        ExchangeRateData containing:
            - source_currency: The base currency
            - exchanged_currency: The target currency
            - valuation_date: The date of the rate
            - rate_value: The exchange rate as Decimal
            - provider_name: The name of the provider used

    Raises:
        ValueError: If the provider is not supported
        APIClientError: If there's an error fetching the data
    """
    adapter = get_adapter(provider)
    return adapter.get_exchange_rate_data(
        source_currency=source_currency,
        exchanged_currency=exchanged_currency,
        valuation_date=valuation_date,
    )
