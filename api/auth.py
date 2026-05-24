import os
from flask import Blueprint, redirect, session
from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.contrib.github import make_github_blueprint, github
from flask_dance.consumer import oauth_authorized
from flask_login import login_user, logout_user, login_required
from models.database import db, User

# ── Google OAuth blueprint – no custom routes ───────────────────
google_bp = make_google_blueprint(
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    scope=["openid", "https://www.googleapis.com/auth/userinfo.email",
           "https://www.googleapis.com/auth/userinfo.profile"]
)

# ── GitHub OAuth blueprint – no custom routes ───────────────────
github_bp = make_github_blueprint(
    client_id=os.getenv("GITHUB_CLIENT_ID"),
    client_secret=os.getenv("GITHUB_CLIENT_SECRET"),
    scope="user:email"
)

auth = Blueprint("auth", __name__)

# ── Handle Google OAuth callback via signal ─────────────────────
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
            email=email,
            name=name,
            avatar_url=avatar_url,
            provider="google",
            provider_id=provider_id
        )
        db.session.add(user)
        db.session.commit()

    login_user(user)
    return False  # let Flask-Dance continue the normal redirect

# ── Handle GitHub OAuth callback via signal ─────────────────────
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
            email=email,
            name=name,
            avatar_url=avatar_url,
            provider="github",
            provider_id=provider_id
        )
        db.session.add(user)
        db.session.commit()

    login_user(user)
    return False

# ── Logout route ─────────────────────────────────────────────────
@auth.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect("/")