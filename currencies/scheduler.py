from zoneinfo import ZoneInfo

from django_celery_beat.models import CrontabSchedule, PeriodicTask

from .tasks import fetch_daily_exchange_rates


def init_daily_exchange_fetch(*args, **kwargs):
    # Create schedule for 7:00 AM UTC
    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="7",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone=ZoneInfo("UTC"),
    )

    # Create or update the periodic task
    PeriodicTask.objects.update_or_create(
        name="Fetch Daily Exchange Rates",
        defaults={
            "task": fetch_daily_exchange_rates.__name__,
            "name": f"{fetch_daily_exchange_rates.__module__}.{fetch_daily_exchange_rates.__name__}",
            "crontab": schedule,
            "enabled": True,
            "description": "Fetches daily exchange rates from active providers",
        },
    )
