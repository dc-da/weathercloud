import io

import pandas as pd
from flask import Blueprint, request, send_file

from ..database import get_connection

bp = Blueprint("export", __name__)


def _query_data(source: str, date_from: str, date_to: str, station_id: str) -> pd.DataFrame:
    table = "rapid_observations" if source == "rapid" else "hourly_observations"
    con = get_connection()
    try:
        df = pd.read_sql(
            f"""SELECT *
                FROM {table}
                WHERE station_id = %s
                  AND observed_at_local::date >= %s
                  AND observed_at_local::date <= %s
                ORDER BY observed_at""",
            con,
            params=[station_id, date_from, date_to],
        )
        return df
    finally:
        con.close()


def _query_daily(date_from: str, date_to: str, station_id: str) -> pd.DataFrame:
    con = get_connection()
    try:
        df = pd.read_sql(
            """SELECT *
               FROM daily_observations
               WHERE station_id = %s
                 AND obs_date >= %s
                 AND obs_date <= %s
               ORDER BY obs_date""",
            con,
            params=[station_id, date_from, date_to],
        )
        return df
    finally:
        con.close()


@bp.route("/api/export/csv")
def export_csv(station_id):
    source = request.args.get("source", "rapid")
    date_from = request.args.get("from")
    date_to = request.args.get("to")
    if not date_from or not date_to:
        return "from and to parameters required", 400

    if source == "daily":
        df = _query_daily(date_from, date_to, station_id)
    else:
        df = _query_data(source, date_from, date_to, station_id)

    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)

    filename = f"weather_{station_id}_{source}_{date_from}_{date_to}.csv"
    return send_file(buf, mimetype="text/csv", as_attachment=True, download_name=filename)


@bp.route("/api/export/xlsx")
def export_xlsx(station_id):
    source = request.args.get("source", "rapid")
    date_from = request.args.get("from")
    date_to = request.args.get("to")
    if not date_from or not date_to:
        return "from and to parameters required", 400

    if source == "daily":
        df = _query_daily(date_from, date_to, station_id)
    else:
        df = _query_data(source, date_from, date_to, station_id)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Data")
    buf.seek(0)

    filename = f"weather_{station_id}_{source}_{date_from}_{date_to}.xlsx"
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )
