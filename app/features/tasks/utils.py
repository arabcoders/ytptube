from app.library.log import get_logger

LOG = get_logger()


def cron_time(timer: str) -> str:
    try:
        from datetime import UTC, datetime

        from cronsim import CronSim

        cs = CronSim(timer, datetime.now(UTC))
        return cs.explain()
    except Exception as exc:
        LOG.exception(
            "Failed to explain task timer '%s'.",
            timer,
            extra={"timer": timer, "exception_type": type(exc).__name__},
        )
        return timer
