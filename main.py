import os
from flask import Flask
from flask_login import LoginManager
from models.database import db, User
from api.routes import router
from api.auth import auth, google_bp, github_bp
from config import DEBUG, BASE_DIR, SECRET_KEY, DATABASE_URL
from extensions import limiter

# ── Create storage folders ────────────────────────────────────────────────────
for folder in ["uploads", "charts", "reports", "logs"]:
    os.makedirs(os.path.join(BASE_DIR, "storage", folder), exist_ok=True)

# ── App factory ───────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key                          = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"]        = 10 * 1024 * 1024   # 10MB
app.config["SQLALCHEMY_DATABASE_URI"]   = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# OAuth over HTTP for local dev only
if DEBUG:
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# ── Extensions ────────────────────────────────────────────────────────────────
db.init_app(app)
limiter.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "router.login_page"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ── Blueprints ────────────────────────────────────────────────────────────────
app.register_blueprint(google_bp, url_prefix="/auth")
app.register_blueprint(github_bp, url_prefix="/auth")
app.register_blueprint(auth)
app.register_blueprint(router)

# ── Create DB tables ──────────────────────────────────────────────────────────
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=DEBUG, port=5000)