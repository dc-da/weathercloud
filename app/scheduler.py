import logging
import threading
import time
from datetime import date, datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import get_all_stations

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None

INTER_STATION_DELAY = 5  # seconds between syncing different stations


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
            _run_rapid_all,
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
            _run_hourly_all,
            "interval",
            hours=interval,
            args=[cfg],
            id="hourly_history",
            name="Hourly History Sync",
            replace_existing=True,
        )
        run_hourly_now = True
        logger.info("Scheduled hourly_history every %d hours", interval)

    # Job 3: Auto-recovery (daily at configured time)
    recovery_cfg = sched_cfg.get("auto_recovery", {})
    if recovery_cfg.get("enabled", False):
        run_at = recovery_cfg.get("run_at", "03:00")
        hour, minute = (int(x) for x in run_at.split(":"))
        _scheduler.add_job(
            _run_auto_recovery,
            CronTrigger(hour=hour, minute=minute),
            args=[cfg],
            id="auto_recovery",
            name="Auto Historical Recovery",
            replace_existing=True,
        )
        logger.info("Scheduled auto_recovery daily at %s", run_at)

        # Check if recovery should run now (missed today's window)
        _maybe_run_recovery_on_startup(cfg)

    _scheduler.start()
    logger.info("Scheduler started")

    # Run first sync immediately in background threads
    if run_rapid_now:
        threading.Thread(target=_run_rapid_all, args=(cfg,), daemon=True).start()
    if run_hourly_now:
        threading.Thread(target=_run_hourly_all, args=(cfg,), daemon=True).start()


def get_scheduler() -> BackgroundScheduler | None:
    return _scheduler


def _run_rapid_all(cfg: dict):
    from .sync.rapid import sync_rapid
    stations = get_all_stations(cfg)
    for i, station in enumerate(stations):
        if i > 0:
            time.sleep(INTER_STATION_DELAY)
        logger.info("Running rapid sync for station %s (%s)", station["id"], station["name"])
        try:
            sync_rapid(cfg, station["id"])
        except Exception:
            logger.exception("Rapid sync failed for station %s", station["id"])


def _run_hourly_all(cfg: dict):
    from .sync.hourly import sync_hourly
    stations = get_all_stations(cfg)
    for i, station in enumerate(stations):
        if i > 0:
            time.sleep(INTER_STATION_DELAY)
        logger.info("Running hourly sync for station %s (%s)", station["id"], station["name"])
        try:
            sync_hourly(cfg, station["id"])
        except Exception:
            logger.exception("Hourly sync failed for station %s", station["id"])


def _run_auto_recovery(cfg: dict):
    """Run auto-recovery in a daemon thread so it doesn't block the scheduler."""
    from .sync.auto_recovery import run_auto_recovery
    logger.info("Starting auto-recovery job")
    try:
        run_auto_recovery(cfg)
    except Exception:
        logger.exception("Auto-recovery job failed")


def _maybe_run_recovery_on_startup(cfg: dict):
    """If the app starts after the scheduled time and recovery hasn't run today, run it now."""
    from .database import get_connection

    today = date.today()
    con = get_connection()
    try:
        cur = con.cursor()
        cur.execute("SELECT 1 FROM recovery_log WHERE run_date = %s", [today])
        row = cur.fetchone()
        cur.close()
    except Exception:
        row = None
    finally:
        con.close()

    if row is None:
        logger.info("Auto-recovery hasn't run today — scheduling deferred startup run")
        # Delay 60s to let rapid/hourly sync start first (they are more important)
        threading.Timer(60.0, _run_auto_recovery, args=[cfg]).start()
