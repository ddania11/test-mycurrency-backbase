from decimal import ROUND_HALF_UP, Decimal

from django import forms
from django.contrib import admin
from django.shortcuts import render
from django.urls import path
from django.utils import timezone

from currencies.services.exchange_rate import ExchangeRateService

from .models import Currency, CurrencyExchangeRate, Provider


class ConverterForm(forms.Form):
    source_currency = forms.ModelChoiceField(
        queryset=Currency.objects.filter(is_active=True),
        label="Source Currency",
        empty_label="Select Source Currency",
    )
    amount = forms.DecimalField(
        max_digits=20, decimal_places=4, min_value=0.0001, initial=1.0
    )
    target_currencies = forms.ModelMultipleChoiceField(
        queryset=Currency.objects.filter(is_active=True),
        label="Target Currencies",
        widget=forms.CheckboxSelectMultiple,
    )


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    """Admin interface for Currency model."""

    list_display = ["code", "name", "symbol", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["code", "name"]
    ordering = ["code"]
    readonly_fields = ["created_at", "updated_at"]
    change_list_template = "admin/currencies/currency/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "converter/",
                self.admin_site.admin_view(self.converter_view),
                name="currency-converter",
            ),
        ]
        return custom_urls + urls

    def converter_view(self, request):
        context = dict(
            self.admin_site.each_context(request),
            title="Currency Converter",
            opts=self.model._meta,
        )

        if request.method == "POST":
            form = ConverterForm(request.POST)
            if form.is_valid():
                source = form.cleaned_data["source_currency"]
                amount = form.cleaned_data["amount"]
                targets = form.cleaned_data["target_currencies"]

                results = []
                service = ExchangeRateService()
                today = timezone.now().date()
                precision = Decimal("0.000001")

                for target in targets:
                    try:
                        rate_data = service.get_exchange_rate(
                            source_currency=source.code,
                            exchanged_currency=target.code,
                            valuation_date=today,
                        )

                        if rate_data:
                            rate_value = Decimal(str(rate_data.rate_value)).quantize(
                                precision, rounding=ROUND_HALF_UP
                            )
                            converted_amount = (amount * rate_value).quantize(
                                precision, rounding=ROUND_HALF_UP
                            )

                            results.append(
                                {
                                    "target": target,
                                    "rate": rate_value,
                                    "converted": converted_amount,
                                    "date": rate_data.valuation_date,
                                }
                            )
                        else:
                            results.append(
                                {
                                    "target": target,
                                    "error": f"No exchange rate found for {today}.",
                                }
                            )
                    except Exception as e:
                        results.append(
                            {
                                "target": target,
                                "error": f"Error: {str(e)}",
                            }
                        )

                context["results"] = results
                context["source_currency"] = source
                context["amount"] = amount
        else:
            form = ConverterForm()

        context["form"] = form
        return render(request, "admin/currencies/currency/converter.html", context)

    fieldsets = [
        (None, {"fields": ["code", "name", "symbol"]}),
        ("Status", {"fields": ["is_active"]}),
        (
            "Timestamps",
            {"fields": ["created_at", "updated_at"], "classes": ["collapse"]},
        ),
    ]


@admin.register(CurrencyExchangeRate)
class CurrencyExchangeRateAdmin(admin.ModelAdmin):
    """Admin interface for CurrencyExchangeRate model."""

    list_display = [
        "get_pair",
        "rate_value",
        "valuation_date",
        "provider",
        "created_at",
    ]
    list_filter = ["source_currency", "valuation_date", "provider"]
    search_fields = [
        "source_currency__code",
        "exchanged_currency__code",
    ]
    ordering = ["-valuation_date", "source_currency__code"]
    date_hierarchy = "valuation_date"
    readonly_fields = ["created_at"]
    autocomplete_fields = ["source_currency", "exchanged_currency"]

    fieldsets = [
        (
            None,
            {"fields": ["source_currency", "exchanged_currency", "valuation_date"]},
        ),
        ("Rate", {"fields": ["rate_value"]}),
        ("Metadata", {"fields": ["provider", "created_at"]}),
    ]

    @admin.display(description="Currency Pair")
    def get_pair(self, obj: CurrencyExchangeRate) -> str:
        """Display the currency pair."""
        return f"{obj.source_currency.code} → {obj.exchanged_currency.code}"


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    """
    Admin interface for Provider model.

    Allows runtime management of exchange rate providers:
    - Activate/deactivate providers
    - Change priorities
    - Configure API keys and URLs
    """

    Provider._meta.get_field("is_active").verbose_name = "Status"

    list_display = [
        "name",
        "display_name",
        "priority",
        "is_active",
        "timeout_seconds",
        "updated_at",
    ]
    list_filter = ["is_active"]
    search_fields = ["name", "display_name"]
    ordering = ["priority", "name"]
    readonly_fields = ["created_at", "updated_at"]
    list_editable = ["priority", "is_active"]

    fieldsets = [
        (None, {"fields": ["name", "display_name"]}),
        (
            "Configuration",
            {
                "fields": ["api_key", "api_url", "timeout_seconds"],
                "description": "API configuration for this provider",
            },
        ),
        (
            "Priority & Status",
            {
                "fields": ["priority", "is_active"],
                "description": "Lower priority numbers are tried first. "
                "Inactive providers are skipped.",
            },
        ),
        (
            "Timestamps",
            {"fields": ["created_at", "updated_at"], "classes": ["collapse"]},
        ),
    ]

    def formfield_for_dbfield(self, db_field, **kwargs):
        """Render is_active as a dropdown instead of a checkbox."""
        if db_field.name == "is_active":
            kwargs["widget"] = forms.Select(
                choices=[(True, "Active"), (False, "Inactive")]
            )
        return super().formfield_for_dbfield(db_field, **kwargs)

    actions = ["activate_providers", "deactivate_providers"]

    @admin.action(description="Activate selected providers")
    def activate_providers(self, request, queryset):
        """Bulk activate providers."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} provider(s) activated.")

    @admin.action(description="Deactivate selected providers")
    def deactivate_providers(self, request, queryset):
        """Bulk deactivate providers."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} provider(s) deactivated.")
