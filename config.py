import os
from dotenv import load_dotenv

ENV = os.getenv("ENV", "development")

if ENV == "production":
    load_dotenv(".env.production")
else:
    load_dotenv(".env.development") or load_dotenv(".env")

# LLM
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME   = os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")

# App limits
MAX_ROWS           = int(os.getenv("MAX_ROWS", 10000))
MAX_CHARTS         = int(os.getenv("MAX_CHARTS", 20))
ALLOWED_EXTENSIONS = [".csv", ".xlsx", ".xls"]
DEBUG              = ENV == "development"

# Auth
SECRET_KEY            = os.getenv("SECRET_KEY", "dev-secret-change-in-prod")
GOOGLE_CLIENT_ID      = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET  = os.getenv("GOOGLE_CLIENT_SECRET")
GITHUB_CLIENT_ID      = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET  = os.getenv("GITHUB_CLIENT_SECRET")

# Database
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'insight.db')}")
# Render gives postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Storage paths
UPLOAD_PATH  = os.path.join(BASE_DIR, "storage", "uploads")
CHARTS_PATH  = os.path.join(BASE_DIR, "storage", "charts")
REPORTS_PATH = os.path.join(BASE_DIR, "storage", "reports")
LOGS_PATH    = os.path.join(BASE_DIR, "storage", "logs")

# Usage limits per tier
TIER_LIMITS = {
    "free":    {"reports_per_month": 3,  "max_rows": 1000},
    "starter": {"reports_per_month": 20, "max_rows": 10000},
    "pro":     {"reports_per_month": 999,"max_rows": 10000},
}