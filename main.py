import os
from flask import Flask, redirect, session
from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.contrib.github import make_github_blueprint, github
from flask_dance.consumer import oauth_authorized
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from api.routes import router
from config import DEBUG, BASE_DIR
from models.database import db, User

# Create storage folders
for folder in ["uploads", "charts", "reports", "logs"]:
    os.makedirs(os.path.join(BASE_DIR, "storage", folder), exist_ok=True)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

# Database initialization
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'insight.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "/login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ── OAuth blueprints ──────────────────────────────────────────────
google_bp = make_google_blueprint(
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    scope=["openid", "https://www.googleapis.com/auth/userinfo.email",
           "https://www.googleapis.com/auth/userinfo.profile"]
)
github_bp = make_github_blueprint(
    client_id=os.getenv("GITHUB_CLIENT_ID"),
    client_secret=os.getenv("GITHUB_CLIENT_SECRET"),
    scope="user:email"
)

app.register_blueprint(router)
app.register_blueprint(google_bp, url_prefix="/auth/google")
app.register_blueprint(github_bp, url_prefix="/auth/github")

# ── OAuth signals (handle user creation after successful login) ───
@oauth_authorized.connect_via(google_bp)
def google_logged_in(blueprint, token):
    if not token:
        return False
    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        return False
    info = resp.json()
    email = info.get("email")
    name = info.get("name", email)
    avatar_url = info.get("picture", "")
    provider_id = info.get("id")
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(
            email=email, name=name, avatar_url=avatar_url,
            provider="google", provider_id=provider_id
        )
        db.session.add(user)
        db.session.commit()
    login_user(user)
    return False

@oauth_authorized.connect_via(github_bp)
def github_logged_in(blueprint, token):
    if not token:
        return False
    resp = github.get("/user")
    if not resp.ok:
        return False
    info = resp.json()
    name = info.get("name") or info.get("login")
    avatar_url = info.get("avatar_url", "")
    provider_id = str(info.get("id"))
    email = info.get("email")
    if not email:
        emails_resp = github.get("/user/emails")
        if emails_resp.ok:
            emails = emails_resp.json()
            primary = next((e["email"] for e in emails if e.get("primary")), None)
            email = primary or f"github_{provider_id}@noreply.github.com"
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(
            email=email, name=name, avatar_url=avatar_url,
            provider="github", provider_id=provider_id
        )
        db.session.add(user)
        db.session.commit()
    login_user(user)
    return False

# ── Logout route (simple, no blueprint) ─────────────────────────
@app.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect("/")

# ── Debug route (optional) ──────────────────────────────────────
@app.route("/debug/routes")
def debug_routes():
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append(f"{rule.endpoint} -> {rule.rule}")
    return "<br>".join(sorted(routes))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=DEBUG, port=5000)