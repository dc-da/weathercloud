import logging
import threading

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def init_scheduler(app):
    global _scheduler
    cfg = app.config["WS"]
    sched_cfg = cfg.get("scheduler", {})

    _scheduler = BackgroundScheduler(daemon=True)

    run_rapid_now = False
    run_hourly_now = False

    # Job 1: Rapid history (every N hours)
    rapid_cfg = sched_cfg.get("rapid_history", {})
    if rapid_cfg.get("enabled", False):
        interval = rapid_cfg.get("interval_hours", 4)
        _scheduler.add_job(
            _run_rapid,
            "interval",
            hours=interval,
            args=[cfg],
            id="rapid_history",
            name="Rapid History Sync",
            replace_existing=True,
        )
        run_rapid_now = True
        logger.info("Scheduled rapid_history every %d hours", interval)

    # Job 2: Hourly history (every N hours)
    hourly_cfg = sched_cfg.get("hourly_history", {})
    if hourly_cfg.get("enabled", False):
        interval = hourly_cfg.get("interval_hours", 12)
        _scheduler.add_job(
            _run_hourly,
            "interval",
            hours=interval,
            args=[cfg],
            id="hourly_history",
            name="Hourly History Sync",
            replace_existing=True,
        )
        run_hourly_now = True
        logger.info("Scheduled hourly_history every %d hours", interval)

    _scheduler.start()
    logger.info("Scheduler started")

    # Run first sync immediately in background threads so the DB gets
    # populated right away instead of waiting for the first interval.
    if run_rapid_now:
        threading.Thread(target=_run_rapid, args=(cfg,), daemon=True).start()
    if run_hourly_now:
        threading.Thread(target=_run_hourly, args=(cfg,), daemon=True).start()


def get_scheduler() -> BackgroundScheduler | None:
    return _scheduler


def _run_rapid(cfg: dict):
    from .sync.rapid import sync_rapid
    logger.info("Running scheduled rapid sync")
    sync_rapid(cfg)


def _run_hourly(cfg: dict):
    from .sync.hourly import sync_hourly
    logger.info("Running scheduled hourly sync")
    sync_hourly(cfg)
