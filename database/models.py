"""ORM models: users, messages, model_logs, feedback."""
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from database.db import db


def utcnow() -> datetime:
    """Naive UTC timestamp (stored as UTC in MySQL)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(dt):
    return dt.isoformat() + "Z" if dt else None


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user", server_default="user")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    messages = db.relationship("Message", back_populates="user", passive_deletes=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "email": self.email,
                "role": self.role, "created_at": iso(self.created_at)}


class Message(db.Model):
    __tablename__ = "messages"
    __table_args__ = (
        db.Index("ix_messages_user_created", "user_id", "created_at"),
        db.Index("ix_messages_prediction", "prediction"),
        db.Index("ix_messages_created_at", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    message_text = db.Column(db.Text, nullable=False)
    prediction = db.Column(db.String(10), nullable=False)  # 'spam' | 'ham'
    confidence_score = db.Column(db.Float, nullable=False)  # 0..1, confidence in the predicted class
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", back_populates="messages")
    feedback = db.relationship("Feedback", back_populates="message",
                               cascade="all, delete-orphan", passive_deletes=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "message_text": self.message_text,
            "prediction": self.prediction,
            "confidence_score": round(self.confidence_score, 4),
            "confidence_percent": round(self.confidence_score * 100, 2),
            "created_at": iso(self.created_at),
        }


class ModelLog(db.Model):
    __tablename__ = "model_logs"

    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(100), nullable=False)
    accuracy = db.Column(db.Float, nullable=False)
    precision = db.Column(db.Float, nullable=False)
    recall = db.Column(db.Float, nullable=False)
    f1_score = db.Column(db.Float, nullable=False)
    trained_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def to_dict(self) -> dict:
        return {"id": self.id, "model_name": self.model_name, "accuracy": self.accuracy,
                "precision": self.precision, "recall": self.recall,
                "f1_score": self.f1_score, "trained_at": iso(self.trained_at)}


class Feedback(db.Model):
    __tablename__ = "feedback"

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey("messages.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    user_feedback = db.Column(db.String(20), nullable=False)  # 'correct' | 'incorrect'
    comments = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    message = db.relationship("Message", back_populates="feedback")

    def to_dict(self) -> dict:
        return {"id": self.id, "message_id": self.message_id,
                "user_feedback": self.user_feedback, "comments": self.comments,
                "created_at": iso(self.created_at)}
