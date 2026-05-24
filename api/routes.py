import os
import glob
import uuid
from flask import Blueprint, request, jsonify, send_file, send_from_directory
from werkzeug.utils import secure_filename
from config import UPLOAD_PATH, CHARTS_PATH
from utils.file_handler import load_file
from utils.data_cleaner import clean
from utils.logger import get_logger
from core.profiler import profile
from core.llm_analyst import analyse
from core.chart_engine import generate_charts
from core.narrator import narrate
from core.report_builder import build

router = Blueprint("router", __name__)


# ── Error codes ───────────────────────────────────────────────────────────────
def _error(code: str, message: str, report_id: str = None, status: int = 500):
    payload = {
        "error":     True,
        "code":      code,
        "message":   message,
    }
    if report_id:
        payload["report_id"] = report_id
    return jsonify(payload), status


# ── Cleanup helper ────────────────────────────────────────────────────────────
def _cleanup(filepath: str, report_id: str, log) -> None:
    """Delete uploaded file and chart PNGs after report is built."""
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            log(f"Cleaned up upload: {os.path.basename(filepath)}")
    except Exception as e:
        log(f"WARNING: Could not delete upload file: {e}")

    try:
        pngs = glob.glob(os.path.join(CHARTS_PATH, f"{report_id}_*.png"))
        for png in pngs:
            os.remove(png)
        if pngs:
            log(f"Cleaned up {len(pngs)} chart PNG(s).")
    except Exception as e:
        log(f"WARNING: Could not delete chart PNGs: {e}")


# ── Frontend routes ───────────────────────────────────────────────────────────
@router.route("/")
def index():
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
    return send_from_directory(frontend_path, "index.html")


@router.route("/style.css")
def styles():
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
    return send_from_directory(frontend_path, "style.css")


# ── Upload route ──────────────────────────────────────────────────────────────
@router.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return _error("NO_FILE", "No file was uploaded.", status=400)

    file = request.files["file"]

    if file.filename == "":
        return _error("EMPTY_FILENAME", "Uploaded file has no name.", status=400)

    report_id = str(uuid.uuid4())[:8]
    log       = get_logger(report_id)
    filepath  = None

    log(f"Report {report_id} started.")
    log(f"File received: {file.filename}")

    # Sanitize filename to prevent path traversal
    safe_name = secure_filename(file.filename)
    filename  = f"{report_id}_{safe_name}"
    filepath  = os.path.join(UPLOAD_PATH, filename)
    file.save(filepath)

    try:
        df = load_file(filepath)
        log(f"File loaded. Shape: {df.shape[0]} rows x {df.shape[1]} columns.")

        df = clean(df)
        log(f"Data cleaned. Shape after cleaning: {df.shape[0]} rows x {df.shape[1]} columns.")

        prof = profile(df)
        log(f"Dataset profiled. Columns: {', '.join(prof['columns'])}")

        plan = analyse(prof)
        log(f"LLM identified domain as: '{plan['domain']}'")
        log(f"Report title: '{plan['report_title']}'")
        log(f"LLM suggested {len(plan['charts'])} charts: {', '.join([c['title'] for c in plan['charts']])}")

        charts = generate_charts(df, plan, report_id, log)
        log(f"All {len(charts)} charts generated and saved.")

        stories = narrate(charts, log)
        log(f"Narration complete for all {len(stories)} charts.")

        pdf_path = build(charts, stories, plan, report_id)
        log(f"PDF built successfully: {pdf_path}")

        _cleanup(filepath, report_id, log)
        log(f"Report {report_id} completed. Ready for download.")

        return jsonify({
            "report_id":  report_id,
            "report_url": f"/report/{report_id}"
        })

    except ValueError as e:
        log(f"VALIDATION ERROR: {str(e)}")
        _cleanup(filepath, report_id, log)
        return _error("VALIDATION_ERROR", str(e), report_id, status=400)

    except Exception as e:
        import traceback
        traceback.print_exc()
        log(f"ERROR: {str(e)}")
        _cleanup(filepath, report_id, log)

        # Map known error types to specific codes
        msg = str(e)
        if "json" in msg.lower() or "parse" in msg.lower():
            return _error("LLM_PARSE_FAILURE",
                          "Could not parse LLM response. Please try again.",
                          report_id)
        if "groq" in msg.lower() or "rate" in msg.lower():
            return _error("LLM_RATE_LIMIT",
                          "LLM API rate limit hit. Please wait a moment and try again.",
                          report_id)
        if "pdf" in msg.lower():
            return _error("PDF_BUILD_FAILURE",
                          "Failed to build the PDF report. Please try again.",
                          report_id)

        return _error("INTERNAL_ERROR",
                      "Something went wrong. Please try again.",
                      report_id)


# ── Report download route ─────────────────────────────────────────────────────
@router.route("/report/<report_id>", methods=["GET"])
def get_report(report_id):
    from config import REPORTS_PATH

    # Sanitize report_id — only allow alphanumeric
    if not report_id.isalnum():
        return _error("INVALID_ID", "Invalid report ID.", status=400)

    path = os.path.join(REPORTS_PATH, f"{report_id}.pdf")
    if not os.path.exists(path):
        return _error("NOT_FOUND", "Report not found.", status=404)

    return send_file(path, as_attachment=True)