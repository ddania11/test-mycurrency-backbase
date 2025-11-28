from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from currencies.models import Currency, CurrencyExchangeRate
from currencies.services.exchange_rate import ExchangeRateService
from currencies.tasks import backfill_exchange_rates

from .serializers import (
    CurrencyConversionRequestSerializer,
    CurrencyConversionResponseSerializer,
    CurrencyListSerializer,
    CurrencySerializer,
    ExchangeRateListRequestSerializer,
    ExchangeRateSerializer,
    ExchangeRateTimeSeriesSerializer,
)


class CurrencyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Currency CRUD operations.

    Endpoints:
    - GET /api/currencies/ - List all currencies
    - POST /api/currencies/ - Create a currency
    - GET /api/currencies/{code}/ - Retrieve a currency
    - PUT /api/currencies/{code}/ - Update a currency
    - PATCH /api/currencies/{code}/ - Partial update
    - DELETE /api/currencies/{code}/ - Delete a currency
    """

    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer
    lookup_field = "code"
    lookup_value_regex = r"[A-Z]{3}"

    def get_serializer_class(self):
        """Use lightweight serializer for list action."""
        if self.action == "list":
            return CurrencyListSerializer
        return CurrencySerializer

    def get_queryset(self):
        """Filter by is_active if specified."""
        queryset = super().get_queryset()
        is_active = self.request.query_params.get("is_active")

        if is_active is not None:
            is_active = is_active.lower() in ("true", "1", "yes")
            queryset = queryset.filter(is_active=is_active)

        return queryset.order_by("code")


class ExchangeRateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Exchange Rate operations.

    Endpoints:
    - GET /api/rates/ - List all exchange rates
    - GET /api/rates/{id}/ - Retrieve a rate
    - GET /api/rates/timeseries/ - Get time series for a currency pair
    """

    queryset = CurrencyExchangeRate.objects.select_related(
        "source_currency",
        "exchanged_currency",
    ).order_by("-valuation_date")
    serializer_class = ExchangeRateSerializer

    def get_queryset(self):
        """Apply filters from query params."""
        queryset = super().get_queryset()

        source = self.request.query_params.get("source_currency")
        target = self.request.query_params.get("exchanged_currency")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")

        if source:
            queryset = queryset.filter(source_currency__code=source.upper())
        if target:
            queryset = queryset.filter(exchanged_currency__code=target.upper())
        if date_from:
            queryset = queryset.filter(valuation_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(valuation_date__lte=date_to)

        return queryset

    @action(detail=False, methods=["GET"])
    def timeseries(self, request: Request) -> Response:
        """
        Get exchange rate time series for a currency pair.

        Query Parameters:
        - source_currency: Source currency code (required)
        - exchanged_currency: Target currency code (required)
        - date_from: Start date (optional)
        - date_to: End date (optional)

        Returns:
        - List of {valuation_date, rate_value}
        """
        serializer = ExchangeRateListRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        source = serializer.validated_data["source_currency"]
        target = serializer.validated_data["exchanged_currency"]
        date_from = serializer.validated_data.get("date_from")
        date_to = serializer.validated_data.get("date_to")

        rates_data = CurrencyExchangeRate.objects.get_timeseries(
            source_currency=source,
            exchanged_currency=target,
            date_from=date_from,
            date_to=date_to,
        )

        if not rates_data and date_from and date_to:
            backfill_exchange_rates.delay(
                source_currency_code=source,
                target_currency_code=target,
                date_from=date_from,
                date_to=date_to,
            )

        response_serializer = ExchangeRateTimeSeriesSerializer(rates_data, many=True)

        return Response(
            {
                "source_currency": source,
                "exchanged_currency": target,
                "date_from": date_from,
                "date_to": date_to,
                "count": len(response_serializer.data),
                "rates": response_serializer.data,
            }
        )


class CurrencyConversionView(APIView):
    """
    API View for currency conversion.

    POST /api/convert/
    Converts an amount from one currency to another.

    Request Body:
    - source_currency: Source currency code
    - exchanged_currency: Target currency code
    - amount: Amount to convert

    Response:
    - Original amount and currencies
    - Converted amount
    - Exchange rate used
    - Valuation date
    - Provider used
    """

    def post(self, request: Request) -> Response:
        """Convert currency amount."""
        serializer = CurrencyConversionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        source = serializer.validated_data["source_currency"]
        target = serializer.validated_data["exchanged_currency"]
        amount = serializer.validated_data["amount"]

        # Get today's rate using the service
        service = ExchangeRateService()
        today = timezone.now().date()

        try:
            rate_data = service.get_exchange_rate(
                source_currency=source,
                exchanged_currency=target,
                valuation_date=today,
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to get exchange rate: {str(e)}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if rate_data is None:
            return Response(
                {
                    "error": f"Exchange rate not available for "
                    f"{source}/{target} on {today}"
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Calculate converted amount
        precision = Decimal("0.000001")

        rate_value = Decimal(str(rate_data.rate_value)).quantize(
            precision, rounding=ROUND_HALF_UP
        )
        converted_amount: Decimal = (amount * rate_value).quantize(
            precision, rounding=ROUND_HALF_UP
        )

        response_data = {
            "source_currency": source,
            "exchanged_currency": target,
            "amount": amount,
            "converted_amount": converted_amount,
            "rate": rate_value,
            "valuation_date": rate_data.valuation_date,
        }

        response_serializer = CurrencyConversionResponseSerializer(data=response_data)
        response_serializer.is_valid(raise_exception=True)

        return Response(response_serializer.data)
