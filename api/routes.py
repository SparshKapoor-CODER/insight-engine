import os
import uuid
from flask import Blueprint, request, jsonify, send_file, send_from_directory
from config import UPLOAD_PATH
from utils.file_handler import load_file
from utils.data_cleaner import clean
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

    file = request.files["file"]
    report_id = str(uuid.uuid4())[:8]

    # Save uploaded file
    filename = f"{report_id}_{file.filename}"
    filepath = os.path.join(UPLOAD_PATH, filename)
    file.save(filepath)

    try:
        df       = load_file(filepath)
        df       = clean(df)
        prof     = profile(df)
        plan     = analyse(prof)
        charts   = generate_charts(df, plan, report_id)
        stories  = narrate(charts)
        pdf_path = build(charts, stories, plan, report_id)

        return jsonify({
            "report_id": report_id,
            "report_url": f"/report/{report_id}"
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@router.route("/report/<report_id>", methods=["GET"])
def get_report(report_id):
    from config import REPORTS_PATH
    path = os.path.join(REPORTS_PATH, f"{report_id}.pdf")
    if not os.path.exists(path):
        return jsonify({"error": "Report not found"}), 404
    return send_file(path, as_attachment=True)