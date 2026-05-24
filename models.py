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
    provider    = db.Column(db.String(20))   # 'google' or 'github'
    provider_id = db.Column(db.String(100))
    tier        = db.Column(db.String(20), default="free")
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    reports     = db.relationship("Report", backref="user", lazy=True)

    def reports_this_month(self):
        from sqlalchemy import extract
        now = datetime.utcnow()
        return Report.query.filter_by(user_id=self.id).filter(
            extract("month", Report.created_at) == now.month,
            extract("year",  Report.created_at) == now.year
        ).count()


class Report(db.Model):
    __tablename__ = "reports"

    id         = db.Column(db.String(8), primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    filename   = db.Column(db.String(255))
    status     = db.Column(db.String(20), default="completed")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)