import os
from flask import Blueprint, redirect, url_for, flash, session
from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.contrib.github import make_github_blueprint, github
from flask_login import login_user, logout_user, login_required
from models.database import db, User

# ── OAuth blueprints ──────────────────────────────────────────────────────────
google_bp = make_google_blueprint(
    client_id     = os.getenv("GOOGLE_CLIENT_ID"),
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET"),
    scope         = ["openid", "https://www.googleapis.com/auth/userinfo.email",
                     "https://www.googleapis.com/auth/userinfo.profile"],
    redirect_url  = "/auth/google/authorized"
)

github_bp = make_github_blueprint(
    client_id     = os.getenv("GITHUB_CLIENT_ID"),
    client_secret = os.getenv("GITHUB_CLIENT_SECRET"),
    scope         = "user:email",
    redirect_url  = "/auth/github/authorized"
)

auth = Blueprint("auth", __name__)


# ── Google callback ───────────────────────────────────────────────────────────
@auth.route("/auth/google/authorized")
def google_authorized():
    if not google.authorized:
        return redirect(url_for("google.login"))

    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        return redirect("/login?error=google_failed")

    info       = resp.json()
    email      = info.get("email")
    name       = info.get("name", email)
    avatar_url = info.get("picture", "")
    provider_id = info.get("id")

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(
            email       = email,
            name        = name,
            avatar_url  = avatar_url,
            provider    = "google",
            provider_id = provider_id
        )
        db.session.add(user)
        db.session.commit()

    login_user(user)
    return redirect("/dashboard")


# ── GitHub callback ───────────────────────────────────────────────────────────
@auth.route("/auth/github/authorized")
def github_authorized():
    if not github.authorized:
        return redirect(url_for("github.login"))

    resp = github.get("/user")
    if not resp.ok:
        return redirect("/login?error=github_failed")

    info        = resp.json()
    name        = info.get("name") or info.get("login")
    avatar_url  = info.get("avatar_url", "")
    provider_id = str(info.get("id"))

    # GitHub may not expose email — fetch it separately
    email = info.get("email")
    if not email:
        emails_resp = github.get("/user/emails")
        if emails_resp.ok:
            emails = emails_resp.json()
            primary = next((e["email"] for e in emails if e.get("primary")), None)
            email   = primary or f"github_{provider_id}@noreply.github.com"

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(
            email       = email,
            name        = name,
            avatar_url  = avatar_url,
            provider    = "github",
            provider_id = provider_id
        )
        db.session.add(user)
        db.session.commit()

    login_user(user)
    return redirect("/dashboard")


# ── Logout ────────────────────────────────────────────────────────────────────
@auth.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect("/")