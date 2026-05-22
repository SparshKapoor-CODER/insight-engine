import os
import uuid
from flask import Blueprint, request, jsonify, send_file, send_from_directory
from config import UPLOAD_PATH
from utils.file_handler import load_file
from utils.data_cleaner import clean
from utils.logger import get_logger
from core.profiler import profile
from core.llm_analyst import analyse
from core.chart_engine import generate_charts
from core.narrator import narrate
from core.report_builder import build

router = Blueprint("router", __name__)


@router.route("/")
def index():
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
    return send_from_directory(frontend_path, "index.html")


@router.route("/style.css")
def styles():
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
    return send_from_directory(frontend_path, "style.css")


@router.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file      = request.files["file"]
    report_id = str(uuid.uuid4())[:8]
    log       = get_logger(report_id)

    log(f"Report {report_id} started.")
    log(f"File received: {file.filename}")

    filename = f"{report_id}_{file.filename}"
    filepath = os.path.join(UPLOAD_PATH, filename)
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
        log(f"Report {report_id} completed. Ready for download.")

        return jsonify({
            "report_id":  report_id,
            "report_url": f"/report/{report_id}"
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        log(f"ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500


@router.route("/report/<report_id>", methods=["GET"])
def get_report(report_id):
    from config import REPORTS_PATH
    path = os.path.join(REPORTS_PATH, f"{report_id}.pdf")
    if not os.path.exists(path):
        return jsonify({"error": "Report not found"}), 404
    return send_file(path, as_attachment=True)
