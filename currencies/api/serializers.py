from decimal import Decimal
from typing import Any

from rest_framework import serializers

from currencies.models import Currency, CurrencyExchangeRate, Provider


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ["code", "name", "symbol", "is_active", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class CurrencyListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ["code", "name", "symbol"]


class ProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Provider
        fields = ["name", "display_name", "is_active", "priority"]


class ExchangeRateSerializer(serializers.ModelSerializer):
    source_currency = serializers.SlugRelatedField(
        slug_field="code", queryset=Currency.objects.all()
    )
    exchanged_currency = serializers.SlugRelatedField(
        slug_field="code", queryset=Currency.objects.all()
    )
    provider = serializers.SlugRelatedField(
        slug_field="name", queryset=Provider.objects.all(), required=False
    )

    class Meta:
        model = CurrencyExchangeRate
        fields = [
            "id",
            "source_currency",
            "exchanged_currency",
            "valuation_date",
            "rate_value",
            "provider",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ExchangeRateTimeSeriesSerializer(serializers.Serializer):
    valuation_date = serializers.DateField()
    rate_value = serializers.DecimalField(max_digits=18, decimal_places=6)


class ExchangeRateListRequestSerializer(serializers.Serializer):
    source_currency = serializers.CharField(
        max_length=3,
        help_text="Source currency code (e.g., EUR)",
    )
    exchanged_currency = serializers.CharField(
        max_length=3,
        help_text="Target currency code (e.g., USD)",
    )
    date_from = serializers.DateField(
        required=False,
        help_text="Start date for time series (inclusive)",
    )
    date_to = serializers.DateField(
        required=False,
        help_text="End date for time series (inclusive)",
    )

    def validate_source_currency(self, value: str) -> str:
        """Validate source currency exists."""
        value = value.upper()
        if not Currency.objects.filter(code=value, is_active=True).exists():
            raise serializers.ValidationError(
                f"Currency '{value}' not found or inactive."
            )
        return value

    def validate_exchanged_currency(self, value: str) -> str:
        """Validate exchanged currency exists."""
        value = value.upper()
        if not Currency.objects.filter(code=value, is_active=True).exists():
            raise serializers.ValidationError(
                f"Currency '{value}' not found or inactive."
            )
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Cross-field validation."""
        if attrs.get("source_currency") == attrs.get("exchanged_currency"):
            raise serializers.ValidationError(
                "Source and exchanged currencies must be different."
            )

        date_from = attrs.get("date_from")
        date_to = attrs.get("date_to")

        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError(
                "date_from must be before or equal to date_to."
            )

        return attrs


class CurrencyConversionRequestSerializer(serializers.Serializer):
    source_currency = serializers.CharField(
        max_length=3,
        help_text="Source currency code (e.g., EUR)",
    )
    exchanged_currency = serializers.CharField(
        max_length=3,
        help_text="Target currency code (e.g., USD)",
    )
    amount = serializers.DecimalField(
        max_digits=18,
        decimal_places=6,
        min_value=Decimal("0.000001"),
        help_text="Amount to convert",
    )

    def validate_source_currency(self, value: str) -> str:
        """Validate source currency exists."""
        value = value.upper()
        if not Currency.objects.filter(code=value, is_active=True).exists():
            raise serializers.ValidationError(
                f"Currency '{value}' not found or inactive."
            )
        return value

    def validate_exchanged_currency(self, value: str) -> str:
        """Validate exchanged currency exists."""
        value = value.upper()
        if not Currency.objects.filter(code=value, is_active=True).exists():
            raise serializers.ValidationError(
                f"Currency '{value}' not found or inactive."
            )
        return value


class CurrencyConversionResponseSerializer(serializers.Serializer):
    source_currency = serializers.CharField()
    exchanged_currency = serializers.CharField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=6)
    converted_amount = serializers.DecimalField(max_digits=18, decimal_places=6)
    rate = serializers.DecimalField(max_digits=18, decimal_places=6)
    valuation_date = serializers.DateField()
