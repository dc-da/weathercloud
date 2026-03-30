from flask import Blueprint, current_app, jsonify, render_template

from ..sync.auto_recovery import get_recovery_status, run_auto_recovery

bp = Blueprint("recovery", __name__)


@bp.route("/recovery")
def recovery_view():
    return render_template("recovery.html")


@bp.route("/api/recovery/status")
def api_recovery_status():
    data = get_recovery_status()
    # Serialize dates/timestamps to strings
    for entry in data["queue"]:
        for k, v in entry.items():
            if v is not None and not isinstance(v, (str, int, float, bool)):
                entry[k] = str(v)
    for entry in data["recent_runs"]:
        for k, v in entry.items():
            if v is not None and not isinstance(v, (str, int, float, bool)):
                entry[k] = str(v)
    return jsonify(data)


@bp.route("/api/recovery/run-now", methods=["POST"])
def api_recovery_run_now():
    """Manually trigger a recovery run."""
    cfg = current_app.config["WS"]
    sched_cfg = cfg.get("scheduler", {}).get("auto_recovery", {})
    if not sched_cfg.get("enabled", False):
        return jsonify({"error": "Auto-recovery is disabled in config"}), 400

    import threading
    threading.Thread(target=run_auto_recovery, args=(cfg,), daemon=True).start()
    return jsonify({"status": "started"})
