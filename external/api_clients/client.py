import hashlib
import json
import logging
from typing import Any

import requests
from django.core.cache import cache

from .exceptions import (
    APIAuthenticationError,
    APIClientError,
    APIConnectionError,
    APINotFoundError,
    APIRateLimitError,
    APIResponseError,
    APITimeoutError,
)

logger = logging.getLogger(__name__)


class APIClient:
    """
    Base API client that provides HTTP methods with caching and error handling.
    """

    base_url: str = ""

    def __init__(
        self,
        api_key: str | None = None,
        timeout: int = 30,
        cache_enabled: bool = True,
        cache_prefix: str = "api_client",
    ):
        self.api_key = api_key
        self.timeout = timeout
        self.cache_enabled = cache_enabled
        self.cache_prefix = cache_prefix
        self._session = requests.Session()

    def _get_default_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _get_default_params(self) -> dict[str, Any]:
        return {}

    def _build_url(self, endpoint: str) -> str:
        base = self.base_url.rstrip("/")
        endpoint = endpoint.lstrip("/")
        return f"{base}/{endpoint}"

    def _build_cache_key(
        self, method: str, endpoint: str, params: dict | None = None
    ) -> str:
        """
        Build a unique cache key for the request.

        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters

        Returns:
            A unique cache key string
        """
        key_data = {
            "method": method,
            "url": self._build_url(endpoint),
            "params": params or {},
        }
        key_hash = hashlib.md5(
            json.dumps(key_data, sort_keys=True).encode()
        ).hexdigest()
        return f"{self.cache_prefix}:{self.__class__.__name__}:{key_hash}"

    def _get_from_cache(self, cache_key: str) -> Any | None:
        """Get a value from the cache."""
        if not self.cache_enabled:
            return None
        return cache.get(cache_key)

    def _set_cache(self, cache_key: str, value: Any, ttl: int) -> None:
        """Set a value in the cache."""
        if self.cache_enabled and ttl > 0:
            cache.set(cache_key, value, ttl)

    def _handle_response(self, response: requests.Response) -> Any:
        """
        Handle the API response and raise appropriate exceptions.

        Args:
            response: The requests Response object

        Returns:
            The parsed JSON response

        Raises:
            APIAuthenticationError: If authentication fails (401)
            APINotFoundError: If resource not found (404)
            APIRateLimitError: If rate limit exceeded (429)
            APIResponseError: For other error status codes
        """
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError:
            status_code = response.status_code

            try:
                error_body = response.json()
                error_message = error_body.get(
                    "message", error_body.get("error", str(error_body))
                )
            except (ValueError, KeyError):
                error_message = response.text or f"HTTP {status_code} error"

            if status_code == 401:
                raise APIAuthenticationError(error_message)
            elif status_code == 404:
                raise APINotFoundError(error_message)
            elif status_code == 429:
                retry_after = response.headers.get("Retry-After")
                raise APIRateLimitError(
                    error_message,
                    retry_after=int(retry_after) if retry_after else None,
                )
            else:
                raise APIResponseError(error_message, status_code=status_code)
        except ValueError as e:
            raise APIResponseError(f"Invalid JSON response: {e}")

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        data: dict | None = None,
        json_data: dict | None = None,
        headers: dict | None = None,
        cache: bool = False,
        cache_ttl: int = 3600,
        **kwargs,
    ) -> Any:
        """
        Make an HTTP request to the API.

        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE)
            endpoint: API endpoint (will be appended to base_url)
            params: Query parameters
            data: Form data for the request body
            json_data: JSON data for the request body
            headers: Additional headers (merged with defaults)
            cache: Whether to cache this request (only for GET)
            cache_ttl: Cache time-to-live in seconds
            **kwargs: Additional arguments passed to requests

        Returns:
            The parsed JSON response

        Raises:
            APIClientError: For any API-related errors
        """
        # Build URL
        url = self._build_url(endpoint)

        # Merge headers
        request_headers = self._get_default_headers()
        if headers:
            request_headers.update(headers)

        # Merge params
        request_params = self._get_default_params()
        if params:
            request_params.update(params)

        # Check cache for GET requests
        if method.upper() == "GET" and cache:
            cache_key = self._build_cache_key(method, endpoint, request_params)
            cached_response = self._get_from_cache(cache_key)
            if cached_response is not None:
                logger.debug(f"Cache hit for {url}")
                return cached_response

        # Make the request
        logger.debug(f"Making {method} request to {url}")

        try:
            response = self._session.request(
                method=method.upper(),
                url=url,
                params=request_params,
                data=data,
                json=json_data,
                headers=request_headers,
                timeout=self.timeout,
                **kwargs,
            )
        except requests.exceptions.Timeout:
            raise APITimeoutError(f"Request to {url} timed out after {self.timeout}s")
        except requests.exceptions.ConnectionError as e:
            raise APIConnectionError(f"Connection error to {url}: {e}")
        except requests.exceptions.RequestException as e:
            raise APIClientError(f"Request failed: {e}")

        # Handle response
        result = self._handle_response(response)

        # Cache successful GET responses
        if method.upper() == "GET" and cache:
            self._set_cache(cache_key, result, cache_ttl)
            logger.debug(f"Cached response for {url} with TTL {cache_ttl}s")

        return result

    # HTTP method shortcuts

    def get(
        self,
        endpoint: str,
        params: dict | None = None,
        headers: dict | None = None,
        cache: bool = True,
        cache_ttl: int = 3600,
        **kwargs,
    ) -> Any:
        """
        Make a GET request.

        Args:
            endpoint: API endpoint
            params: Query parameters
            headers: Additional headers
            cache: Whether to cache the response
            cache_ttl: Cache TTL in seconds
            **kwargs: Additional arguments

        Returns:
            The parsed JSON response
        """
        return self._request(
            method="GET",
            endpoint=endpoint,
            params=params,
            headers=headers,
            cache=cache,
            cache_ttl=cache_ttl,
            **kwargs,
        )

    def post(
        self,
        endpoint: str,
        data: dict | None = None,
        json_data: dict | None = None,
        params: dict | None = None,
        headers: dict | None = None,
        **kwargs,
    ) -> Any:
        """
        Make a POST request.

        Args:
            endpoint: API endpoint
            data: Form data
            json_data: JSON data
            params: Query parameters
            headers: Additional headers
            **kwargs: Additional arguments

        Returns:
            The parsed JSON response
        """
        return self._request(
            method="POST",
            endpoint=endpoint,
            params=params,
            data=data,
            json_data=json_data,
            headers=headers,
            **kwargs,
        )

    def put(
        self,
        endpoint: str,
        data: dict | None = None,
        json_data: dict | None = None,
        params: dict | None = None,
        headers: dict | None = None,
        **kwargs,
    ) -> Any:
        """
        Make a PUT request.

        Args:
            endpoint: API endpoint
            data: Form data
            json_data: JSON data
            params: Query parameters
            headers: Additional headers
            **kwargs: Additional arguments

        Returns:
            The parsed JSON response
        """
        return self._request(
            method="PUT",
            endpoint=endpoint,
            params=params,
            data=data,
            json_data=json_data,
            headers=headers,
            **kwargs,
        )

    def patch(
        self,
        endpoint: str,
        data: dict | None = None,
        json_data: dict | None = None,
        params: dict | None = None,
        headers: dict | None = None,
        **kwargs,
    ) -> Any:
        """
        Make a PATCH request.

        Args:
            endpoint: API endpoint
            data: Form data
            json_data: JSON data
            params: Query parameters
            headers: Additional headers
            **kwargs: Additional arguments

        Returns:
            The parsed JSON response
        """
        return self._request(
            method="PATCH",
            endpoint=endpoint,
            params=params,
            data=data,
            json_data=json_data,
            headers=headers,
            **kwargs,
        )

    def delete(
        self,
        endpoint: str,
        params: dict | None = None,
        headers: dict | None = None,
        **kwargs,
    ) -> Any:
        """
        Make a DELETE request.

        Args:
            endpoint: API endpoint
            params: Query parameters
            headers: Additional headers
            **kwargs: Additional arguments

        Returns:
            The parsed JSON response
        """
        return self._request(
            method="DELETE",
            endpoint=endpoint,
            params=params,
            headers=headers,
            **kwargs,
        )

    def close(self) -> None:
        """Close the underlying session."""
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
