from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel, ValidationError

from external.api_clients.exceptions import APIResponseError

if TYPE_CHECKING:
    from external.api_clients.currencybeacon.client import CurrencyBeaconClient

T = TypeVar("T", bound=BaseModel)


class BaseService:
    def __init__(self, client: CurrencyBeaconClient) -> None:
        """
        Initialize the service with a shared client.

        Args:
            client: The CurrencyBeaconClient instance to use for API calls
        """
        self._client = client

    def _parse_response(self, response: dict[str, Any], model: type[T]) -> T:
        """
        Parse and validate an API response using a Pydantic model.

        Args:
            response: Raw API response dictionary
            model: Pydantic model class to validate against

        Returns:
            Validated Pydantic model instance

        Raises:
            APIResponseError: If the response doesn't match the expected schema
        """

        def parse_date_field(val):
            if isinstance(val, str):
                try:
                    return datetime.fromisoformat(val).date()
                except ValueError:
                    return val
            return val

        if model.__name__ == "ExchangeRateResponse":
            if "date" in response:
                response["date"] = parse_date_field(response["date"])
        elif model.__name__ == "TimeSeriesResponse":
            if "start_date" in response:
                response["start_date"] = parse_date_field(response["start_date"])
            if "end_date" in response:
                response["end_date"] = parse_date_field(response["end_date"])
        elif model.__name__ == "ConvertResponse":
            if "date" in response:
                response["date"] = parse_date_field(response["date"])

        try:
            return model.model_validate(response)
        except ValidationError as e:
            raise APIResponseError(
                f"Invalid response from CurrencyBeacon API: {e}"
            ) from e
