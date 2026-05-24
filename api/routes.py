import os
import glob
import uuid
from flask import Blueprint, request, jsonify, send_file, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from config import UPLOAD_PATH, CHARTS_PATH, TIER_LIMITS
from models.database import db, Report
from utils.file_handler import load_file
from utils.data_cleaner import clean
from utils.logger import get_logger
from core.profiler import profile
from core.llm_analyst import analyse
from core.chart_engine import generate_charts
from core.narrator import narrate
from core.report_builder import build

router = Blueprint("router", __name__)


# ── Error helper ──────────────────────────────────────────────────────────────
def _error(code, message, report_id=None, status=500):
    payload = {"error": True, "code": code, "message": message}
    if report_id:
        payload["report_id"] = report_id
    return jsonify(payload), status


# ── Cleanup helper ────────────────────────────────────────────────────────────
def _cleanup(filepath, report_id, log):
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            log(f"Cleaned up upload: {os.path.basename(filepath)}")
    except Exception as e:
        log(f"WARNING: Could not delete upload: {e}")
    try:
        pngs = glob.glob(os.path.join(CHARTS_PATH, f"{report_id}_*.png"))
        for png in pngs:
            os.remove(png)
        if pngs:
            log(f"Cleaned up {len(pngs)} chart PNG(s).")
    except Exception as e:
        log(f"WARNING: Could not delete PNGs: {e}")


# ── Frontend pages ────────────────────────────────────────────────────────────
@router.route("/")
def index():
    frontend_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
    return send_from_directory(os.path.abspath(frontend_path), "index.html")


@router.route("/login")
def login_page():
    frontend_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
    return send_from_directory(os.path.abspath(frontend_path), "login.html")


@router.route("/dashboard")
@login_required
def dashboard():
    frontend_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
    return send_from_directory(os.path.abspath(frontend_path), "dashboard.html")


@router.route("/style.css")
def styles():
    frontend_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
    return send_from_directory(os.path.abspath(frontend_path), "style.css")


# ── User info API ─────────────────────────────────────────────────────────────
@router.route("/api/me")
@login_required
def me():
    limits       = TIER_LIMITS[current_user.tier]
    used         = current_user.reports_this_month()
    past_reports = Report.query.filter_by(user_id=current_user.id)\
                         .order_by(Report.created_at.desc()).limit(10).all()

    return jsonify({
        "name":       current_user.name,
        "email":      current_user.email,
        "avatar_url": current_user.avatar_url,
        "tier":       current_user.tier,
        "usage": {
            "used":  used,
            "limit": limits["reports_per_month"]
        },
        "reports": [{
            "id":         r.id,
            "filename":   r.filename,
            "title":      r.title,
            "domain":     r.domain,
            "created_at": r.created_at.strftime("%b %d, %Y %H:%M")
        } for r in past_reports]
    })


# ── Health check ──────────────────────────────────────────────────────────────
@router.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


# ── Upload route ──────────────────────────────────────────────────────────────
@router.route("/upload", methods=["POST"])
@login_required
def upload():
    # Check usage quota
    limits = TIER_LIMITS[current_user.tier]
    used   = current_user.reports_this_month()
    if used >= limits["reports_per_month"]:
        return _error(
            "QUOTA_EXCEEDED",
            f"You have used {used}/{limits['reports_per_month']} reports this month. "
            f"Upgrade your plan to generate more.",
            status=403
        )

    if "file" not in request.files:
        return _error("NO_FILE", "No file was uploaded.", status=400)

    file = request.files["file"]
    if file.filename == "":
        return _error("EMPTY_FILENAME", "Uploaded file has no name.", status=400)

    report_id = str(uuid.uuid4())[:8]
    log       = get_logger(report_id)
    filepath  = None

    log(f"Report {report_id} started by user {current_user.email}.")
    log(f"File received: {file.filename}")

    safe_name = secure_filename(file.filename)
    filename  = f"{report_id}_{safe_name}"
    filepath  = os.path.join(UPLOAD_PATH, filename)
    file.save(filepath)

    try:
        df = load_file(filepath)
        log(f"File loaded. Shape: {df.shape[0]} rows x {df.shape[1]} columns.")

        df = clean(df)
        log(f"Data cleaned. Shape: {df.shape[0]} rows x {df.shape[1]} columns.")

        prof = profile(df)
        log(f"Dataset profiled. Columns: {', '.join(prof['columns'])}")

        plan = analyse(prof)
        log(f"LLM domain: '{plan['domain']}' | Title: '{plan['report_title']}'")
        log(f"Charts: {', '.join([c['title'] for c in plan['charts']])}")

        charts  = generate_charts(df, plan, report_id, log)
        stories = narrate(charts, log)
        pdf_path = build(charts, stories, plan, report_id)
        log(f"PDF built: {pdf_path}")

        # Save report record to DB
        report = Report(
            id       = report_id,
            user_id  = current_user.id,
            filename = safe_name,
            title    = plan.get("report_title", "Report"),
            domain   = plan.get("domain", "unknown"),
            status   = "completed"
        )
        db.session.add(report)
        db.session.commit()

        _cleanup(filepath, report_id, log)
        log(f"Report {report_id} completed.")

        return jsonify({
            "report_id":  report_id,
            "report_url": f"/report/{report_id}"
        })

    except ValueError as e:
        log(f"VALIDATION ERROR: {e}")
        _cleanup(filepath, report_id, log)
        return _error("VALIDATION_ERROR", str(e), report_id, status=400)

    except Exception as e:
        import traceback
        traceback.print_exc()
        log(f"ERROR: {e}")
        _cleanup(filepath, report_id, log)
        msg = str(e).lower()
        if "json" in msg or "parse" in msg:
            return _error("LLM_PARSE_FAILURE",
                          "Could not parse LLM response. Please try again.", report_id)
        if "rate" in msg or "groq" in msg:
            return _error("LLM_RATE_LIMIT",
                          "API rate limit hit. Please wait and try again.", report_id)
        return _error("INTERNAL_ERROR", "Something went wrong. Please try again.", report_id)

@app.route("/debug/routes")
def debug_routes():
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append(f"{rule.endpoint} -> {rule.rule}")
    return "<br>".join(routes)


# ── Report download ───────────────────────────────────────────────────────────
@router.route("/report/<report_id>")
@login_required
def get_report(report_id):
    from config import REPORTS_PATH
    if not report_id.isalnum():
        return _error("INVALID_ID", "Invalid report ID.", status=400)

    # Verify this report belongs to the current user
    report = Report.query.filter_by(id=report_id, user_id=current_user.id).first()
    if not report:
        return _error("NOT_FOUND", "Report not found.", status=404)

    path = os.path.join(REPORTS_PATH, f"{report_id}.pdf")
    if not os.path.exists(path):
        return _error("NOT_FOUND", "Report file not found.", status=404)

    return send_file(path, as_attachment=True)


# ── Log viewer ────────────────────────────────────────────────────────────────
@router.route("/logs/<report_id>")
@login_required
def get_log(report_id):
    from config import LOGS_PATH
    if not report_id.isalnum():
        return _error("INVALID_ID", "Invalid report ID.", status=400)

    # Only show logs for reports belonging to current user
    report = Report.query.filter_by(id=report_id, user_id=current_user.id).first()
    if not report:
        return _error("NOT_FOUND", "Log not found.", status=404)

    path = os.path.join(LOGS_PATH, f"{report_id}.log")
    if not os.path.exists(path):
        return _error("NOT_FOUND", "Log file not found.", status=404)

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return f"<pre style='font-family:monospace;padding:24px;'>{content}</pre>", 200