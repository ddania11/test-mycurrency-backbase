import logging
from datetime import date, timedelta

from celery import group, shared_task

from .models import Currency
from .services.exchange_rate import ExchangeRateService

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=3,
)
def fetch_daily_exchange_rates(
    self,
    source_currency: str = "USD",
    valuation_date: str | None = None,
) -> dict:
    """
    Fetch and store daily exchange rates.

    This task fetches rates from the highest priority active provider
    and stores them in the database. It's designed to run daily via
    Celery Beat.

    Args:
        source_currency: Base currency for rates (default: USD)
        valuation_date: Date for rates (default: today). Format: YYYY-MM-DD

    Returns:
        Dict with task result summary
    """
    if valuation_date is None:
        valuation_date = date.today()
    elif isinstance(valuation_date, str):
        valuation_date = date.fromisoformat(valuation_date)

    logger.info(f"Fetching exchange rates for {source_currency} on {valuation_date}")

    # Get all active target currencies
    target_currencies = list(
        Currency.objects.filter(is_active=True)
        .exclude(code=source_currency)
        .values_list("code", flat=True)
    )

    if not target_currencies:
        logger.warning("No active currencies found to fetch rates for")
        return {
            "status": "skipped",
            "reason": "no_active_currencies",
        }

    service = ExchangeRateService()
    stored_currencies = []
    failed_currencies = []

    # Fetch each currency pair - get_exchange_rate stores automatically
    for target_code in target_currencies:
        try:
            rate_data = service.get_exchange_rate(
                source_currency=source_currency,
                exchanged_currency=target_code,
                valuation_date=valuation_date,
            )
            stored_currencies.append(target_code)
            logger.debug(
                f"Fetched rate: {source_currency}→{target_code}={rate_data.rate_value}"
            )
        except Exception as e:
            logger.warning(f"Failed to fetch {source_currency}→{target_code}: {e}")
            failed_currencies.append(target_code)

    logger.info(
        f"Successfully stored {len(stored_currencies)} rates for {source_currency}"
    )

    return {
        "status": "success",
        "source_currency": source_currency,
        "valuation_date": str(valuation_date),
        "rates_stored": len(stored_currencies),
        "currencies": stored_currencies,
        "failed": failed_currencies,
    }


@shared_task(bind=True)
def fetch_exchange_rates_for_pair(
    self,
    source_currency: str,
    exchanged_currency: str,
    valuation_date: str | None = None,
) -> dict:
    """
    Fetch and store exchange rate for a specific currency pair.

    Useful for on-demand rate fetching when a specific pair is needed.

    Args:
        source_currency: Source currency code
        exchanged_currency: Target currency code
        valuation_date: Date for rate (default: today)

    Returns:
        Dict with the fetched rate info
    """
    if valuation_date is None:
        valuation_date = date.today()
    elif isinstance(valuation_date, str):
        valuation_date = date.fromisoformat(valuation_date)

    logger.info(
        f"Fetching rate for {source_currency}/{exchanged_currency} on {valuation_date}"
    )

    service = ExchangeRateService()

    try:
        rate_data = service.get_exchange_rate(
            source_currency=source_currency,
            exchanged_currency=exchanged_currency,
            valuation_date=valuation_date,
        )

        if rate_data:
            return {
                "status": "success",
                "source_currency": source_currency,
                "exchanged_currency": exchanged_currency,
                "rate": str(rate_data.rate_value),
                "valuation_date": str(rate_data.valuation_date),
                "provider": rate_data.provider_name,
            }
        else:
            return {
                "status": "not_found",
                "source_currency": source_currency,
                "exchanged_currency": exchanged_currency,
                "valuation_date": str(valuation_date),
            }

    except Exception as e:
        logger.error(f"Failed to fetch rate: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


@shared_task
def backfill_exchange_rates(
    source_currency: str = "USD",
    days: int = 30,
) -> dict:
    """
    Backfill exchange rates for the past N days.

    Useful for populating historical data or filling gaps.
    Executes tasks asynchronously using a Celery group for maximum efficiency.

    Args:
        source_currency: Base currency for rates
        days: Number of days to backfill

    Returns:
        Summary of backfill dispatch
    """

    logger.info(f"Backfilling {days} days of rates for {source_currency}")

    today = date.today()

    tasks = [
        fetch_daily_exchange_rates.s(
            source_currency=source_currency,
            valuation_date=str(today - timedelta(days=i)),
        )
        for i in range(days)
    ]

    job = group(tasks)
    result = job.apply_async()

    logger.info(f"Dispatched {days} tasks for backfill. Group ID: {result.id}")

    return {
        "status": "dispatched",
        "source_currency": source_currency,
        "days_requested": days,
        "group_id": result.id,
        "message": "Historical data load started in background",
    }
