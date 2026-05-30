import os
import json
from flask import Blueprint, redirect, session
from flask_dance.contrib.google import make_google_blueprint
from flask_dance.contrib.github import make_github_blueprint
from flask_dance.consumer import oauth_authorized
from flask_login import login_user, logout_user, login_required, current_user
from models.database import db, User, OAuthToken
from datetime import datetime

# ── OAuth blueprints ───────────────────────────────────────────────────────
# We intentionally do NOT pass storage=SQLAlchemyStorage here.
# Flask-dance's default session-based storage is used for the OAuth handshake;
# we persist tokens ourselves in _upsert_token() after login_user() so we
# always have a valid user.id to link against. This avoids orphaned NULL-user
# token rows that SQLAlchemyStorage creates when user_required=False.
google_bp = make_google_blueprint(
    client_id     = os.getenv("GOOGLE_CLIENT_ID"),
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET"),
    scope         = ["openid",
                     "https://www.googleapis.com/auth/userinfo.email",
                     "https://www.googleapis.com/auth/userinfo.profile"],
)

github_bp = make_github_blueprint(
    client_id     = os.getenv("GITHUB_CLIENT_ID"),
    client_secret = os.getenv("GITHUB_CLIENT_SECRET"),
    scope         = "user:email",
)

auth = Blueprint("auth", __name__)


# ── Helper: upsert a token row linked to a user ────────────────────────────
def _upsert_token(user, provider, token):
    """
    Change 3 — keep exactly one OAuthToken row per (user, provider).

    Checks whether a row already exists for this user + provider:
      - If yes  -> update the token text and bump updated_at
      - If no   -> insert a new row

    Uses SQLAlchemy only - no raw SQL.
    Because this is called *after* login_user(), user.id is always valid
    and we never create orphaned NULL-user rows.
    """
    token_str = json.dumps(token)

    existing = OAuthToken.query.filter_by(
        user_id  = user.id,
        provider = provider
    ).first()

    if existing:
        existing.token      = token_str
        existing.updated_at = datetime.utcnow()
    else:
        db.session.add(OAuthToken(
            user_id  = user.id,
            provider = provider,
            token    = token_str
        ))

    db.session.commit()


# ── Google authorized signal ───────────────────────────────────────────────
@oauth_authorized.connect_via(google_bp)
def google_logged_in(blueprint, token):
    if not token:
        return redirect("/login")

    resp = blueprint.session.get("/oauth2/v2/userinfo")
    if not resp.ok:
        return redirect("/login")

    info        = resp.json()
    email       = info.get("email")
    name        = info.get("name", email)
    avatar_url  = info.get("picture", "")
    provider_id = str(info.get("id", ""))

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email, name=name, avatar_url=avatar_url,
                    provider="google", provider_id=provider_id)
        db.session.add(user)
        db.session.commit()

    login_user(user)

    # Change 3: upsert token - user.id is now set so no NULL rows
    _upsert_token(user, "google", token)

    return redirect("/dashboard")


# ── GitHub authorized signal ───────────────────────────────────────────────
@oauth_authorized.connect_via(github_bp)
def github_logged_in(blueprint, token):
    if not token:
        return redirect("/login")

    resp = blueprint.session.get("/user")
    if not resp.ok:
        return redirect("/login")

    info        = resp.json()
    name        = info.get("name") or info.get("login")
    avatar_url  = info.get("avatar_url", "")
    provider_id = str(info.get("id", ""))

    email = info.get("email")
    if not email:
        emails_resp = blueprint.session.get("/user/emails")
        if emails_resp.ok:
            emails  = emails_resp.json()
            primary = next((e["email"] for e in emails if e.get("primary")), None)
            email   = primary or f"github_{provider_id}@noreply.github.com"

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email, name=name, avatar_url=avatar_url,
                    provider="github", provider_id=provider_id)
        db.session.add(user)
        db.session.commit()

    login_user(user)

    # Change 3: upsert token - user.id is now set so no NULL rows
    _upsert_token(user, "github", token)

    return redirect("/dashboard")


# ── Logout ─────────────────────────────────────────────────────────────────
@auth.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect("/")