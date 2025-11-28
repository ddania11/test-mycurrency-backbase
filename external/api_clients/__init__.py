from .adapters import ExchangeRateData, get_exchange_rate_data
from .client import APIClient
from .exceptions import (
    APIAuthenticationError,
    APIClientError,
    APIConnectionError,
    APINotFoundError,
    APIRateLimitError,
    APIResponseError,
    APITimeoutError,
)

__all__ = [
    # Main adapter interface
    "get_exchange_rate_data",
    "ExchangeRateData",
    # Base client
    "APIClient",
    # Exceptions
    "APIClientError",
    "APIConnectionError",
    "APITimeoutError",
    "APIResponseError",
    "APIAuthenticationError",
    "APIRateLimitError",
    "APINotFoundError",
]
