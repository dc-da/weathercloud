import os
import logging

from flask import Flask, abort, g, redirect, render_template, request

from .config import get_all_stations, get_primary_station_id, get_station_by_id, load_config
from .database import init_db


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    cfg = load_config()
    app.config["WS"] = cfg

    # Ensure data directory exists
    db_path = cfg["database"]["path"]
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    # Initialize database schema
    init_db(db_path)

    # Register blueprints (all station-scoped under /station/<station_id>)
    from .routes.dashboard import bp as dashboard_bp
    from .routes.daily import bp as daily_bp
    from .routes.historical import bp as historical_bp
    from .routes.reports import bp as reports_bp
    from .routes.sync_api import bp as sync_bp
    from .routes.export import bp as export_bp
    from .routes.home import bp as home_bp
    from .routes.recovery import bp as recovery_bp
    from .routes.gap_fill import bp as gap_fill_bp

    prefix = "/station/<station_id>"
    app.register_blueprint(home_bp)
    app.register_blueprint(recovery_bp)  # global, not station-scoped
    app.register_blueprint(dashboard_bp, url_prefix=prefix)
    app.register_blueprint(daily_bp, url_prefix=prefix)
    app.register_blueprint(historical_bp, url_prefix=prefix)
    app.register_blueprint(reports_bp, url_prefix=prefix)
    app.register_blueprint(sync_bp, url_prefix=prefix)
    app.register_blueprint(export_bp, url_prefix=prefix)
    app.register_blueprint(gap_fill_bp, url_prefix=prefix)

    # ---- before_request: validate station_id for /station/<id>/ routes ----
    @app.before_request
    def resolve_station():
        """For station-scoped routes, validate station_id and inject into g."""
        station_id = request.view_args.get("station_id") if request.view_args else None
        if station_id is None:
            return  # homepage or non-station route
        station = get_station_by_id(cfg, station_id)
        if station is None:
            abort(404, description=f"Station '{station_id}' not found")
        g.station_id = station_id
        g.station = station

    # ---- context processor: inject station info into all templates ----
    @app.context_processor
    def inject_station_context():
        ctx = {"all_stations": get_all_stations(cfg)}
        if hasattr(g, "station_id"):
            ctx["station_id"] = g.station_id
            ctx["station"] = g.station
        return ctx

    # ---- Legacy URL redirects (old bookmarks → primary station) ----
    primary_id = get_primary_station_id(cfg)

    @app.route("/dashboard")
    def legacy_dashboard():
        return redirect(f"/station/{primary_id}/dashboard", code=301)

    @app.route("/daily")
    def legacy_daily():
        return redirect(f"/station/{primary_id}/daily", code=301)

    @app.route("/historical")
    def legacy_historical():
        return redirect(f"/station/{primary_id}/historical", code=301)

    @app.route("/reports")
    def legacy_reports():
        return redirect(f"/station/{primary_id}/reports", code=301)

    @app.route("/sync-status")
    def legacy_sync_status():
        return redirect(f"/station/{primary_id}/sync-status", code=301)

    # Start scheduler (only in the main process, not in reloader)
    if not app.config["WS"]["app"].get("debug") or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        from .scheduler import init_scheduler
        init_scheduler(app)

    return app
