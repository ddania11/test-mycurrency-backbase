from django.core.management.base import BaseCommand

from currencies.models import Currency, Provider


class Command(BaseCommand):
    """Initialize database with default currencies and providers."""

    help = "Initialize database with default currencies and providers"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force recreation of existing records",
        )

    def handle(self, *args, **options):
        force = options["force"]

        self.stdout.write("Initializing currency data...")

        # Default currencies
        currencies = [
            {"code": "USD", "name": "US Dollar", "symbol": "$"},
            {"code": "EUR", "name": "Euro", "symbol": "€"},
            {"code": "GBP", "name": "British Pound", "symbol": "£"},
            {"code": "CHF", "name": "Swiss Franc", "symbol": "CHF"},
        ]

        created_count = 0
        for currency_data in currencies:
            currency, created = (
                Currency.objects.update_or_create(
                    code=currency_data["code"],
                    defaults={
                        "name": currency_data["name"],
                        "symbol": currency_data["symbol"],
                        "is_active": True,
                    },
                )
                if force
                else (
                    Currency.objects.get_or_create(
                        code=currency_data["code"],
                        defaults={
                            "name": currency_data["name"],
                            "symbol": currency_data["symbol"],
                            "is_active": True,
                        },
                    )
                )
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  Created currency: {currency.code}")
                )
            else:
                self.stdout.write(f"  Currency exists: {currency.code}")

        self.stdout.write(f"\nCurrencies: {created_count} created")

        # Default providers
        providers = [
            {
                "name": "currencybeacon",
                "display_name": "CurrencyBeacon",
                "api_url": "https://api.currencybeacon.com/v1",
                "priority": 1,
                "timeout_seconds": 30,
            },
            {
                "name": "mock",
                "display_name": "Mock Provider (Testing)",
                "api_url": "",
                "priority": 999,
                "is_active": False,
                "timeout_seconds": 5,
            },
        ]

        provider_count = 0
        for provider_data in providers:
            provider, created = (
                Provider.objects.update_or_create(
                    name=provider_data["name"],
                    defaults={
                        "display_name": provider_data["display_name"],
                        "api_url": provider_data["api_url"],
                        "priority": provider_data["priority"],
                        "is_active": provider_data.get("is_active", True),
                        "timeout_seconds": provider_data["timeout_seconds"],
                    },
                )
                if force
                else (
                    Provider.objects.get_or_create(
                        name=provider_data["name"],
                        defaults={
                            "display_name": provider_data["display_name"],
                            "api_url": provider_data["api_url"],
                            "priority": provider_data["priority"],
                            "is_active": provider_data.get("is_active", True),
                            "timeout_seconds": provider_data["timeout_seconds"],
                        },
                    )
                )
            )
            if created:
                provider_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  Created provider: {provider.name}")
                )
            else:
                self.stdout.write(f"  Provider exists: {provider.name}")

        self.stdout.write(f"\nProviders: {provider_count} created")

        self.stdout.write(self.style.SUCCESS("\nInitialization complete!"))
        self.stdout.write(
            "\nNote: Set the CURRENCY_BEACON_API_KEY in your Provider's "
            "api_key field via the admin interface or run:"
        )
        self.stdout.write(
            '  Provider.objects.filter(name="currencybeacon")'
            '.update(api_key="your-api-key")'
        )
