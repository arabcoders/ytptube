import logging

LOG: logging.Logger = logging.getLogger(__name__)


def cron_time(timer: str) -> str:
    try:
        from datetime import UTC, datetime

        from cronsim import CronSim

        cs = CronSim(timer, datetime.now(UTC))
        return cs.explain()
    except Exception as exc:
        LOG.exception(exc)
        return timer
