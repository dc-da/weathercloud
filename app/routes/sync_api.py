import json
import time
from datetime import date

from flask import Blueprint, Response, current_app, jsonify, request

from ..database import get_connection
from ..sync.historical import get_backfill_state, get_last_synced_date, request_stop, start_backfill

bp = Blueprint("sync_api", __name__)


@bp.route("/sync-status")
def sync_status_view():
    from flask import render_template
    return render_template("sync_status.html")


@bp.route("/api/sync/historical/start", methods=["POST"])
def api_sync_historical_start():
    cfg = current_app.config["WS"]
    body = request.get_json(silent=True) or {}
    start_date_str = body.get("start_date")

    start_date = None
    if start_date_str:
        try:
            start_date = date.fromisoformat(start_date_str)
        except ValueError:
            return jsonify({"error": "Invalid start_date format (use YYYY-MM-DD)"}), 400

    # If no start_date and no existing data, require it
    if start_date is None:
        station_id = cfg["wu"]["station_id"]
        last = get_last_synced_date(station_id)
        if last is None:
            return jsonify({
                "error": "No existing data. Please provide a start_date.",
                "needs_start_date": True,
            }), 400

    ok = start_backfill(cfg, start_date)
    if not ok:
        return jsonify({"error": "Backfill already running"}), 409

    return jsonify({"status": "started"})


@bp.route("/api/sync/historical/stop", methods=["POST"])
def api_sync_historical_stop():
    request_stop()
    return jsonify({"status": "stop_requested"})


@bp.route("/api/sync/historical/progress")
def api_sync_historical_progress():
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
def api_sync_rapid_run():
    cfg = current_app.config["WS"]
    from ..sync.rapid import sync_rapid
    import threading
    threading.Thread(target=sync_rapid, args=(cfg,), daemon=True).start()
    return jsonify({"status": "started"})


@bp.route("/api/sync/hourly/run", methods=["POST"])
def api_sync_hourly_run():
    cfg = current_app.config["WS"]
    from ..sync.hourly import sync_hourly
    import threading
    threading.Thread(target=sync_hourly, args=(cfg,), daemon=True).start()
    return jsonify({"status": "started"})


@bp.route("/api/sync/status")
def api_sync_status():
    from ..scheduler import get_scheduler

    cfg = current_app.config["WS"]
    station_id = cfg["wu"]["station_id"]

    # Backfill state
    backfill = get_backfill_state()

    # Last synced date for historical
    last_historical = get_last_synced_date(station_id)

    # Scheduler job info
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
def api_sync_log():
    limit = request.args.get("limit", 50, type=int)
    con = get_connection()
    try:
        rows = con.execute(
            """SELECT id, started_at, completed_at, job_type, status,
                      records_fetched, records_inserted, records_updated,
                      date_range_start, date_range_end, error_message, api_calls_made
               FROM sync_log
               ORDER BY started_at DESC
               LIMIT ?""",
            [limit],
        ).fetchall()

        columns = [
            "id", "started_at", "completed_at", "job_type", "status",
            "records_fetched", "records_inserted", "records_updated",
            "date_range_start", "date_range_end", "error_message", "api_calls_made",
        ]
        data = [dict(zip(columns, [str(v) if v is not None else None for v in row])) for row in rows]
        return jsonify(data)
    finally:
        con.close()
