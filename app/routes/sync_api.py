import json
import logging
import time
from datetime import date, timedelta

from flask import Blueprint, Response, current_app, jsonify, render_template, request

from ..api_client import WUClient
from ..database import get_connection
from ..sync.historical import get_backfill_state, get_last_synced_date, request_stop, start_backfill

logger = logging.getLogger(__name__)

bp = Blueprint("sync_api", __name__)


@bp.route("/sync-status")
def sync_status_view(station_id):
    return render_template("sync_status.html")


@bp.route("/api/sync/historical/start", methods=["POST"])
def api_sync_historical_start(station_id):
    cfg = current_app.config["WS"]
    body = request.get_json(silent=True) or {}
    start_date_str = body.get("start_date")
    end_date_str = body.get("end_date")

    start_date = None
    end_date = None

    if start_date_str:
        try:
            start_date = date.fromisoformat(start_date_str)
        except ValueError:
            return jsonify({"error": "Invalid start_date format (use YYYY-MM-DD)"}), 400

    if end_date_str:
        try:
            end_date = date.fromisoformat(end_date_str)
        except ValueError:
            return jsonify({"error": "Invalid end_date format (use YYYY-MM-DD)"}), 400

    # If no start_date and no existing data, require it
    if start_date is None:
        last = get_last_synced_date(station_id)
        if last is None:
            return jsonify({
                "error": "No existing data. Please provide a start_date.",
                "needs_start_date": True,
            }), 400

    ok = start_backfill(cfg, station_id, start_date, end_date)
    if not ok:
        return jsonify({"error": "Backfill already running"}), 409

    return jsonify({"status": "started"})


@bp.route("/api/sync/historical/detect-start", methods=["POST"])
def api_sync_historical_detect_start(station_id):
    """Binary search to find the earliest date with data for this station."""
    cfg = current_app.config["WS"]
    client = WUClient(cfg)
    today = date.today()

    has_any = False
    hi_years = 10

    for years_back in range(10, -1, -1):
        probe = today - timedelta(days=years_back * 365)
        if client.has_data_on_date(station_id, probe):
            hi_years = years_back
            has_any = True
            break

    if not has_any:
        return jsonify({"error": "No data found in the last 10 years", "found": False}), 404

    search_start = today - timedelta(days=hi_years * 365)
    step = 30
    while step >= 1:
        probe = search_start - timedelta(days=step)
        if probe < today - timedelta(days=3660):
            break
        if client.has_data_on_date(station_id, probe):
            search_start = probe
            step = step * 2
        else:
            break

    no_data_date = search_start - timedelta(days=max(step, 1))
    has_data_date = search_start

    while (has_data_date - no_data_date).days > 1:
        mid = no_data_date + timedelta(days=(has_data_date - no_data_date).days // 2)
        if client.has_data_on_date(station_id, mid):
            has_data_date = mid
        else:
            no_data_date = mid
        time.sleep(0.3)

    return jsonify({
        "found": True,
        "start_date": has_data_date.isoformat(),
    })


@bp.route("/api/sync/historical/stop", methods=["POST"])
def api_sync_historical_stop(station_id):
    request_stop()
    return jsonify({"status": "stop_requested"})


@bp.route("/api/sync/historical/progress")
def api_sync_historical_progress(station_id):
    """Server-Sent Events stream for backfill progress."""
    def generate():
        while True:
            state = get_backfill_state()
            yield f"data: {json.dumps(state)}\n\n"
            if not state["running"]:
                break
            time.sleep(1)

    return Response(generate(), mimetype="text/event-stream")


@bp.route("/api/sync/rapid/run", methods=["POST"])
def api_sync_rapid_run(station_id):
    cfg = current_app.config["WS"]
    from ..sync.rapid import sync_rapid
    import threading
    threading.Thread(target=sync_rapid, args=(cfg, station_id), daemon=True).start()
    return jsonify({"status": "started"})


@bp.route("/api/sync/hourly/run", methods=["POST"])
def api_sync_hourly_run(station_id):
    cfg = current_app.config["WS"]
    from ..sync.hourly import sync_hourly
    import threading
    threading.Thread(target=sync_hourly, args=(cfg, station_id), daemon=True).start()
    return jsonify({"status": "started"})


@bp.route("/api/sync/status")
def api_sync_status(station_id):
    from ..scheduler import get_scheduler

    backfill = get_backfill_state()
    last_historical = get_last_synced_date(station_id)

    scheduler = get_scheduler()
    jobs = []
    if scheduler:
        for job in scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
            })

    return jsonify({
        "backfill": backfill,
        "last_historical_date": str(last_historical) if last_historical else None,
        "scheduled_jobs": jobs,
    })


@bp.route("/api/sync/log")
def api_sync_log(station_id):
    limit = request.args.get("limit", 50, type=int)
    con = get_connection()
    try:
        rows = con.execute(
            """SELECT id, started_at, completed_at, job_type, status,
                      records_fetched, records_inserted, records_updated,
                      date_range_start, date_range_end, error_message, api_calls_made,
                      station_id
               FROM sync_log
               WHERE station_id = ? OR station_id IS NULL
               ORDER BY started_at DESC
               LIMIT ?""",
            [station_id, limit],
        ).fetchall()

        columns = [
            "id", "started_at", "completed_at", "job_type", "status",
            "records_fetched", "records_inserted", "records_updated",
            "date_range_start", "date_range_end", "error_message", "api_calls_made",
            "station_id",
        ]
        data = [dict(zip(columns, [str(v) if v is not None else None for v in row])) for row in rows]
        return jsonify(data)
    finally:
        con.close()
