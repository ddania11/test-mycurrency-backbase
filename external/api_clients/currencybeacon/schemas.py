from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class CurrencyInfo(BaseModel):
    """Schema for a single currency."""

    id: int
    name: str
    short_code: str
    code: str | None = None
    symbol: str = ""
    symbol_first: bool = True
    decimal_mark: str = "."
    thousands_separator: str = ","


class ExchangeRateResponse(BaseModel):
    """Schema for latest/historical exchange rates response."""

    date: date
    base: str
    rates: dict[str, float]


class ConvertResponse(BaseModel):
    """Schema for currency conversion response."""

    date: date
    from_currency: str = Field(alias="from")
    to: str
    amount: float
    value: float


class TimeSeriesResponse(BaseModel):
    """Schema for time series exchange rates response."""

    start_date: date
    end_date: date
    base: str
    rates: dict[str, dict[str, float]]  # date -> {currency: rate}


class CurrenciesResponse(BaseModel):
    """Schema for currencies list response."""

    response: list[CurrencyInfo]


class APIMetaResponse(BaseModel):
    """
    Generic wrapper for API responses that include metadata.
    Some endpoints return data wrapped in a 'response' key.
    """

    meta: dict[str, Any] | None = None
    response: Any = None
