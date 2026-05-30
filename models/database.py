from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id          = db.Column(db.Integer, primary_key=True)
    email       = db.Column(db.String(255), unique=True, nullable=False)
    name        = db.Column(db.String(255))
    avatar_url  = db.Column(db.String(500))
    provider    = db.Column(db.String(20))
    provider_id = db.Column(db.String(100))
    tier        = db.Column(db.String(20), default="free")
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    reports     = db.relationship("Report", backref="user", lazy=True)

    def reports_this_month(self):
        now   = datetime.utcnow()
        start = now.replace(day=1, hour=0, minute=0, second=0)
        return Report.query.filter_by(user_id=self.id).filter(
            Report.created_at >= start
        ).count()


class OAuthToken(db.Model):
    __tablename__ = "oauth_tokens"

    id         = db.Column(db.Integer, primary_key=True)
    # Change 3: link every token row to the owning user
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    provider   = db.Column(db.String(20), nullable=False)
    token      = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    # Convenience back-reference
    user = db.relationship("User", backref=db.backref("oauth_tokens", lazy=True))

    __table_args__ = (
        # Enforce at most one token row per (user, provider) pair
        db.UniqueConstraint("user_id", "provider", name="uq_oauth_user_provider"),
    )


class Report(db.Model):
    __tablename__ = "reports"

    id         = db.Column(db.String(8), primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    filename   = db.Column(db.String(255))
    title      = db.Column(db.String(255))
    domain     = db.Column(db.String(100))
    status     = db.Column(db.String(20), default="completed")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Change 4: persist PDF bytes in the DB so reports survive dyno restarts
    pdf_data   = db.Column(db.LargeBinary, nullable=True)