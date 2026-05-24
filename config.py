import os
from dotenv import load_dotenv

# Load environment-specific .env file
ENV = os.getenv("ENV", "development")

if ENV == "production":
    load_dotenv(".env.production")
else:
    load_dotenv(".env.development") or load_dotenv(".env")

GROQ_API_KEY       = os.getenv("GROQ_API_KEY")
MODEL_NAME         = os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")
MAX_ROWS           = int(os.getenv("MAX_ROWS", 10000))
MAX_CHARTS         = int(os.getenv("MAX_CHARTS", 20))
ALLOWED_EXTENSIONS = [".csv", ".xlsx", ".xls"]
DEBUG              = ENV == "development"

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
UPLOAD_PATH  = os.path.join(BASE_DIR, "storage", "uploads")
CHARTS_PATH  = os.path.join(BASE_DIR, "storage", "charts")
REPORTS_PATH = os.path.join(BASE_DIR, "storage", "reports")
LOGS_PATH    = os.path.join(BASE_DIR, "storage", "logs")