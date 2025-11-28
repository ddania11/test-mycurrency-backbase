from django.db import models

from .managers import CurrencyExchangeRateManager, CurrencyManager, ProviderManager


class Currency(models.Model):
    code = models.CharField(
        max_length=3,
        unique=True,
        help_text="ISO 4217 currency code (e.g., USD, EUR)",
    )
    name = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Full currency name",
    )
    symbol = models.CharField(
        max_length=10,
        help_text="Currency symbol (e.g., $, €, £)",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this currency is active in the system",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CurrencyManager()

    class Meta:
        verbose_name = "Currency"
        verbose_name_plural = "Currencies"
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        self.code = self.code.upper()
        super().save(*args, **kwargs)


class CurrencyExchangeRate(models.Model):
    source_currency = models.ForeignKey(
        Currency,
        related_name="exchanges",
        on_delete=models.CASCADE,
        help_text="The base currency",
    )
    exchanged_currency = models.ForeignKey(
        Currency,
        related_name="exchanged_rates",
        on_delete=models.CASCADE,
        help_text="The target currency",
    )
    provider = models.ForeignKey(
        "Provider",
        related_name="providers",
        on_delete=models.CASCADE,
        help_text="The provider",
    )
    valuation_date = models.DateField(
        db_index=True,
        help_text="Date of the exchange rate",
    )
    rate_value = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        db_index=True,
        help_text="Exchange rate value",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CurrencyExchangeRateManager()

    class Meta:
        verbose_name = "Currency Exchange Rate"
        verbose_name_plural = "Currency Exchange Rates"
        ordering = ["-valuation_date", "source_currency__code"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_currency", "exchanged_currency", "valuation_date"],
                name="unique_exchange_rate_per_day",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.source_currency.code} → {self.exchanged_currency.code}: "
            f"{self.rate_value} ({self.valuation_date})"
        )


class Provider(models.Model):
    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique identifier for the provider (e.g., 'currencybeacon')",
    )
    display_name = models.CharField(
        max_length=100,
        help_text="Human-readable provider name",
    )
    api_key = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="API key for authentication (if required)",
    )
    api_url = models.URLField(
        blank=True,
        default="",
        help_text="Base URL for the provider's API",
    )
    priority = models.PositiveIntegerField(
        default=1,
        db_index=True,
        help_text="Provider priority (1 = highest). Lower numbers are tried first.",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this provider is currently active",
    )
    timeout_seconds = models.PositiveIntegerField(
        default=30,
        help_text="Request timeout in seconds",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProviderManager()

    class Meta:
        verbose_name = "Provider"
        verbose_name_plural = "Providers"
        ordering = ["priority", "name"]

    def __str__(self) -> str:
        status = "✓" if self.is_active else "✗"
        return f"{self.display_name} (priority: {self.priority}) [{status}]"
