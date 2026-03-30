from flask import Blueprint, current_app, g, jsonify, render_template

from ..config import get_primary_station_id
from ..sync.gap_fill import get_gap_fill_summary, run_gap_fill

bp = Blueprint("gap_fill", __name__)


@bp.route("/gap-fill")
def gap_fill_view(station_id):
    cfg = current_app.config["WS"]
    primary_id = get_primary_station_id(cfg)
    if station_id != primary_id:
        return "Gap-fill is only available for the primary station", 403
    return render_template("gap_fill.html")


@bp.route("/api/gap-fill/status")
def api_gap_fill_status(station_id):
    cfg = current_app.config["WS"]
    primary_id = get_primary_station_id(cfg)
    if station_id != primary_id:
        return jsonify({"error": "Only available for primary station"}), 403

    summary = get_gap_fill_summary(station_id, cfg)
    return jsonify(summary)


@bp.route("/api/gap-fill/run", methods=["POST"])
def api_gap_fill_run(station_id):
    cfg = current_app.config["WS"]
    primary_id = get_primary_station_id(cfg)
    if station_id != primary_id:
        return jsonify({"error": "Only available for primary station"}), 403

    result = run_gap_fill(station_id, cfg)
    return jsonify(result)
