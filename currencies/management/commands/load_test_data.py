import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from currencies.models import Currency, CurrencyExchangeRate, Provider


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Number of days of history to generate (default: 30)",
        )
        parser.add_argument(
            "--source",
            type=str,
            default="USD",
            help="Source currency code (default: USD)",
        )
        parser.add_argument(
            "--currencies",
            nargs="+",
            default=[
                "EUR",
                "GBP",
                "CHF",
            ],
            help="Target currency codes (default: EUR GBP CHF)",
        )

    def handle(self, *args, **options):
        days = options["days"]
        source_code = options["source"]
        target_codes = options["currencies"]

        self.stdout.write(f"Generating {days} days of data for {source_code}...")

        provider, _ = Provider.objects.get_or_create(
            name="mock",
            defaults={
                "display_name": "Mock Provider",
                "is_active": True,
                "priority": 0,
            },
        )

        source_currency, _ = Currency.objects.get_or_create(
            code=source_code, defaults={"name": source_code, "symbol": "$"}
        )

        current_rates = {
            code: Decimal(str(random.uniform(0.5, 1.5))) for code in target_codes
        }

        records_created = 0

        today = date.today()

        with transaction.atomic():
            for i in range(days):
                valuation_date = today - timedelta(days=i)

                for target_code in target_codes:
                    target_currency, _ = Currency.objects.get_or_create(
                        code=target_code, defaults={"name": target_code}
                    )

                    change_percent = Decimal(str(random.uniform(-0.02, 0.02)))
                    new_rate = current_rates[target_code] * (1 + change_percent)
                    current_rates[target_code] = new_rate

                    CurrencyExchangeRate.objects.store_rate(
                        source_currency=source_currency,
                        exchanged_currency=target_currency,
                        valuation_date=valuation_date,
                        rate_value=new_rate,
                        provider=provider,
                    )
                    records_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully ingested {records_created} rates for {len(target_codes)} currencies."
            )
        )
