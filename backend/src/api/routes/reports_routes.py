"""
Reports routes blueprint.
Ownership: szbenyx

Endpoints:
  POST /v1/reports/generate - Generate a daily/weekly/monthly report
  GET  /v1/reports/list     - List generated reports
"""
import re
import logging
from datetime import datetime
from pathlib import Path

from flask import Blueprint, request, jsonify, current_app, g

from src.thomas_core.auth.decorators import require_auth

logger = logging.getLogger("looma.reports")
reports_bp = Blueprint("reports", __name__)

# Filename pattern: daily_20260630_2300.md
_FILENAME_RE = re.compile(r"^(daily|weekly|monthly)_(\d{8})_(\d{4})\.md$")


@reports_bp.route("/generate", methods=["POST"])
@require_auth
def generate_report():
    """Generate a report (daily/weekly/monthly)."""
    data = request.get_json() or {}
    report_type = data.get("type", "daily")

    if report_type not in ("daily", "weekly", "monthly"):
        return jsonify(error="bad_request", message="type must be daily, weekly, or monthly"), 400

    try:
        from src.pipeline.report_gen import ReportGenerator
        reporter = ReportGenerator()
        path = reporter.generate_report(report_type)
        return jsonify(type=report_type, path=str(path), status="generated")
    except Exception as e:
        return jsonify(error="generate_failed", message=str(e)), 500


@reports_bp.route("/list", methods=["GET"])
@require_auth
def list_reports():
    """List generated reports from the reports data directory."""
    reports = []

    db_path = current_app.config.get("DATABASE_PATH", "data/looma.db")
    report_dir = Path(db_path).parent / "reports"

    try:
        if not report_dir.is_dir():
            return jsonify(reports=[], total=0)

        for f in sorted(report_dir.glob("*.md"), reverse=True):
            m = _FILENAME_RE.match(f.name)
            if not m:
                continue

            report_type = m.group(1)
            date_str = m.group(2)
            time_str = m.group(3)

            # Parse generated_at as ISO datetime
            try:
                generated_dt = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M")
                generated_at = generated_dt.isoformat()
            except ValueError:
                generated_at = None

            reports.append({
                "type": report_type,
                "path": str(f),
                "status": "generated",
                "generated_at": generated_at,
            })

    except Exception as e:
        logger.error(f"Failed to list reports: {e}")
        return jsonify(error="list_failed", message=str(e)), 500

    return jsonify(reports=reports, total=len(reports))
