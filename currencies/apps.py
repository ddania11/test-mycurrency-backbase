from contextlib import suppress

from django.apps import AppConfig
from django.db.utils import OperationalError, ProgrammingError


class CurrenciesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "currencies"

    def ready(self):
        from .scheduler import init_daily_exchange_fetch

        with suppress(OperationalError, ProgrammingError):
            init_daily_exchange_fetch()
