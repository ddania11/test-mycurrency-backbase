import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from external.api_clients import APIClientError
from external.api_clients.adapters import CurrencyAdapter
from external.api_clients.adapters.base import ExchangeRateData

if TYPE_CHECKING:
    from currencies.models import Provider

logger = logging.getLogger(__name__)


# Registry mapping provider names to adapter classes
ADAPTER_REGISTRY: dict[str, type[CurrencyAdapter]] = {}


def register_adapter(name: str, adapter_class: type[CurrencyAdapter]) -> None:
    """Register an adapter class for a provider name."""
    ADAPTER_REGISTRY[name] = adapter_class


def _initialize_adapters() -> None:
    """Initialize the adapter registry with available adapters."""
    from external.api_clients.adapters.currencybeacon import CurrencyBeaconAdapter
    from external.api_clients.adapters.mock import MockAdapter

    register_adapter("currencybeacon", CurrencyBeaconAdapter)
    register_adapter("mock", MockAdapter)
    # Add more adapters here as they are implemented


_initialize_adapters()


class AllProvidersFailedError(Exception):
    """Raised when all providers fail to return data."""

    def __init__(self, message: str, errors: dict[str, str] | None = None):
        super().__init__(message)
        self.errors = errors or {}


@dataclass
class ProviderResult:
    """Result from a provider call."""

    provider_name: str
    data: ExchangeRateData
    success: bool = True


class ProviderManager:
    """
    Manages calls to external exchange rate providers with resilience.

    Features:
    - Priority-based provider selection (from database)
    - Automatic fallback on failure
    - Configurable per-provider settings
    - Logging and error tracking
    """

    def __init__(self):
        """Initialize the provider manager."""
        self._adapter_cache: dict[str, CurrencyAdapter] = {}

    def _get_active_providers(self) -> list["Provider"]:
        """Get active providers from database, ordered by priority."""
        from currencies.models import Provider

        return list(Provider.objects.get_active_ordered())

    def _get_adapter(self, provider: "Provider") -> CurrencyAdapter:
        """
        Get or create an adapter instance for a provider.

        Args:
            provider: Provider model instance

        Returns:
            Configured CurrencyAdapter instance

        Raises:
            ValueError: If no adapter is registered for the provider
        """
        # Check cache first
        cache_key = f"{provider.name}:{provider.id}"
        if cache_key in self._adapter_cache:
            return self._adapter_cache[cache_key]

        # Get adapter class from registry
        adapter_class = ADAPTER_REGISTRY.get(provider.name)
        if adapter_class is None:
            raise ValueError(
                f"No adapter registered for provider '{provider.name}'. "
                f"Available: {list(ADAPTER_REGISTRY.keys())}"
            )

        # Create adapter with provider configuration
        adapter = adapter_class(api_key=provider.api_key or None)

        # Cache the adapter
        self._adapter_cache[cache_key] = adapter

        return adapter

    def get_exchange_rate_data(
        self,
        source_currency: str,
        exchanged_currency: str,
        valuation_date: date,
        provider_name: str | None = None,
    ) -> ExchangeRateData:
        """
        Get exchange rate from providers with automatic fallback.

        If a specific provider is requested, only that provider is used.
        Otherwise, tries all active providers in priority order until
        one succeeds.

        Args:
            source_currency: Source currency code (e.g., 'USD')
            exchanged_currency: Target currency code (e.g., 'EUR')
            valuation_date: Date for the exchange rate
            provider_name: Optional specific provider to use

        Returns:
            ExchangeRateData with the rate information

        Raises:
            AllProvidersFailedError: If all providers fail
            ValueError: If specified provider is not found or not active
        """
        from currencies.models import Provider

        errors: dict[str, str] = {}

        # If specific provider requested
        if provider_name:
            try:
                provider = Provider.objects.get(name=provider_name, is_active=True)
            except Provider.DoesNotExist:
                raise ValueError(f"Provider '{provider_name}' not found or not active")

            adapter = self._get_adapter(provider)
            return adapter.get_exchange_rate_data(
                source_currency=source_currency,
                exchanged_currency=exchanged_currency,
                valuation_date=valuation_date,
            )

        # Try all active providers in priority order
        providers = self._get_active_providers()

        if not providers:
            raise AllProvidersFailedError(
                "No active providers configured",
                errors={"configuration": "No active providers found in database"},
            )

        for provider in providers:
            try:
                logger.debug(f"Trying provider: {provider.name}")
                adapter = self._get_adapter(provider)

                result = adapter.get_exchange_rate_data(
                    source_currency=source_currency,
                    exchanged_currency=exchanged_currency,
                    valuation_date=valuation_date,
                )

                logger.info(
                    f"Successfully fetched rate from {provider.name}: "
                    f"{source_currency}→{exchanged_currency}={result.rate}"
                )

                return result

            except APIClientError as e:
                error_msg = str(e)
                errors[provider.name] = error_msg
                logger.warning(
                    f"Provider {provider.name} failed: {error_msg}. "
                    f"Trying next provider..."
                )
                continue

            except Exception as e:
                error_msg = f"Unexpected error: {e}"
                errors[provider.name] = error_msg
                logger.exception(f"Provider {provider.name} failed unexpectedly")
                continue

        # All providers failed
        raise AllProvidersFailedError(
            f"All {len(providers)} providers failed to fetch rate for "
            f"{source_currency}→{exchanged_currency} on {valuation_date}",
            errors=errors,
        )

    def get_latest_rates(
        self,
        base_currency: str,
        target_currencies: list[str],
    ) -> dict[str, Decimal]:
        """
        Get latest rates for multiple currencies from a single base.

        Used by the daily cron job to fetch all rates efficiently.

        Args:
            base_currency: Base currency code (e.g., 'USD')
            target_currencies: List of target currency codes

        Returns:
            Dict mapping currency codes to rates

        Raises:
            AllProvidersFailedError: If all providers fail
        """
        errors: dict[str, str] = {}
        providers = self._get_active_providers()

        if not providers:
            raise AllProvidersFailedError(
                "No active providers configured",
                errors={"configuration": "No active providers found in database"},
            )

        for provider in providers:
            try:
                logger.debug(f"Trying provider for bulk rates: {provider.name}")
                adapter = self._get_adapter(provider)

                # Use the rates service to get all rates in one call
                response = adapter.client.rates.get_latest(
                    base=base_currency,
                    symbols=target_currencies,
                )

                logger.info(
                    f"Successfully fetched {len(response.rates)} rates "
                    f"from {provider.name}"
                )

                return {
                    code: Decimal(str(rate)) for code, rate in response.rates.items()
                }

            except Exception as e:
                error_msg = str(e)
                errors[provider.name] = error_msg
                logger.warning(
                    f"Provider {provider.name} failed for bulk rates: {error_msg}"
                )
                continue

        raise AllProvidersFailedError(
            f"All providers failed to fetch rates for {base_currency}",
            errors=errors,
        )

    def clear_adapter_cache(self) -> None:
        """Clear the adapter cache. Useful when provider settings change."""
        self._adapter_cache.clear()


# Global instance for convenience
_provider_manager: ProviderManager | None = None


def get_provider_manager() -> ProviderManager:
    """Get the global ProviderManager instance."""
    global _provider_manager
    if _provider_manager is None:
        _provider_manager = ProviderManager()
    return _provider_manager
