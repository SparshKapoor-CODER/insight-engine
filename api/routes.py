import io
import os
import re
import glob
import uuid
from flask import Blueprint, request, jsonify, send_file, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from markupsafe import escape
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

# Allowed hex color pattern
_HEX_RE = re.compile(r'^#[0-9a-fA-F]{6}$')


# ── Error helper ──────────────────────────────────────────────────────────────
def _error(code, message, report_id=None, status=500):
    payload = {"error": True, "code": code, "message": message}
    if report_id:
        payload["report_id"] = report_id
    return jsonify(payload), status


# ── Cleanup helper ─────────────────────────────────────────────────────────────
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


# ── Frontend pages ─────────────────────────────────────────────────────────────
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


# ── User info API ──────────────────────────────────────────────────────────────
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
        "max_rows": limits["max_rows"],
        "reports": [{
            "id":         r.id,
            "filename":   r.filename,
            "title":      r.title,
            "domain":     r.domain,
            "created_at": r.created_at.strftime("%b %d, %Y %H:%M")
        } for r in past_reports]
    })


# ── Health check ───────────────────────────────────────────────────────────────
@router.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


# ── Upload route ───────────────────────────────────────────────────────────────
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

    # ── Read optional branding fields from form data ─────────────────────────
    company_name    = request.form.get("company_name", "Client").strip() or "Client"
    brand_color_raw = request.form.get("brand_color", "#2563eb").strip()

    # Validate hex color — reject if present but malformed
    if brand_color_raw and not _HEX_RE.match(brand_color_raw):
        return _error(
            "INVALID_BRAND_COLOR",
            "brand_color must be a valid hex color in the format #rrggbb (e.g. #2563eb).",
            status=400
        )
    brand_color_hex = brand_color_raw if brand_color_raw else "#2563eb"

    report_id = str(uuid.uuid4())[:8]
    log       = get_logger(report_id)
    filepath  = None

    log(f"Report {report_id} started by user {current_user.email}.")
    log(f"File received: {file.filename}")
    log(f"Company: '{company_name}' | Brand color: '{brand_color_hex}'")

    safe_name = secure_filename(file.filename)
    filename  = f"{report_id}_{safe_name}"
    filepath  = os.path.join(UPLOAD_PATH, filename)
    file.save(filepath)

    try:
        df = load_file(filepath, max_rows=limits["max_rows"])
        log(f"File loaded. Shape: {df.shape[0]} rows x {df.shape[1]} columns.")

        df = clean(df)
        log(f"Data cleaned. Shape: {df.shape[0]} rows x {df.shape[1]} columns.")

        prof = profile(df)
        log(f"Dataset profiled. Columns: {', '.join(prof['columns'])}")

        plan = analyse(prof)
        log(f"LLM domain: '{plan['domain']}' | Title: '{plan['report_title']}'")
        log(f"Charts: {', '.join([c['title'] for c in plan['charts']])}")

        charts   = generate_charts(df, plan, report_id, log)
        stories  = narrate(charts, log)

        # Pass company_name and brand_color_hex into build()
        pdf_path = build(
            charts, stories, plan, report_id,
            company_name=company_name,
            brand_color_hex=brand_color_hex,
        )

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        log(f"PDF built: {pdf_path}")

        # Save report record to DB
        report = Report(
            id       = report_id,
            user_id  = current_user.id,
            filename = safe_name,
            title    = plan.get("report_title", "Report"),
            domain   = plan.get("domain", "unknown"),
            status   = "completed",
            pdf_data = pdf_bytes
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


# ── Report download ────────────────────────────────────────────────────────────
@router.route("/report/<report_id>")
@login_required
def get_report(report_id):
    from config import REPORTS_PATH
    if not report_id.isalnum():
        return _error("INVALID_ID", "Invalid report ID.", status=400)

    report = Report.query.filter_by(id=report_id, user_id=current_user.id).first()
    if not report:
        return _error("NOT_FOUND", "Report not found.", status=404)

    disk_path = os.path.join(REPORTS_PATH, f"{report_id}.pdf")

    if os.path.exists(disk_path):
        return send_file(disk_path, as_attachment=True,
                         download_name=f"{report_id}.pdf",
                         mimetype="application/pdf")

    if report.pdf_data:
        return send_file(
            io.BytesIO(report.pdf_data),
            as_attachment=True,
            download_name=f"{report_id}.pdf",
            mimetype="application/pdf"
        )

    return _error("NOT_FOUND", "Report file not found.", status=404)


# ── Log viewer ─────────────────────────────────────────────────────────────────
@router.route("/logs/<report_id>")
@login_required
def get_log(report_id):
    from config import LOGS_PATH
    if not report_id.isalnum():
        return _error("INVALID_ID", "Invalid report ID.", status=400)

    report = Report.query.filter_by(id=report_id, user_id=current_user.id).first()
    if not report:
        return _error("NOT_FOUND", "Log not found.", status=404)

    path = os.path.join(LOGS_PATH, f"{report_id}.log")
    if not os.path.exists(path):
        return _error("NOT_FOUND", "Log file not found.", status=404)

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return f"<pre style='font-family:monospace;padding:24px;'>{escape(content)}</pre>", 200