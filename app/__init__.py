import os
import logging

from flask import Flask, redirect, url_for

from .config import load_config
from .database import init_db, get_connection


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

    # Register blueprints
    from .routes.dashboard import bp as dashboard_bp
    from .routes.daily import bp as daily_bp
    from .routes.historical import bp as historical_bp
    from .routes.reports import bp as reports_bp
    from .routes.sync_api import bp as sync_bp
    from .routes.export import bp as export_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(daily_bp)
    app.register_blueprint(historical_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(sync_bp)
    app.register_blueprint(export_bp)

    @app.route("/")
    def index():
        return redirect(url_for("dashboard.dashboard_view"))

    # Start scheduler (only in the main process, not in reloader)
    if not app.config["WS"]["app"].get("debug") or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        from .scheduler import init_scheduler
        init_scheduler(app)

    return app
