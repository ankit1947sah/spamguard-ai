"""POST /api/predict and the public summary counters for the home page."""
import re

from flask import Blueprint, current_app, jsonify, request, session
from sqlalchemy import func

from database.db import db
from database.models import Message
from ml_model.predict import classifier
from routes.auth import error

prediction_bp = Blueprint("prediction", __name__, url_prefix="/api")

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

SPAM_ADVICE = ("Do not click links, reply, or share personal or financial details. "
               "Delete the message and block the sender if it looks suspicious.")
HAM_NOTE = "This message looks like a normal, legitimate message."
DISCLAIMER = ("Confidence is a model score estimated from patterns in training data, "
              "not a guarantee that a message is safe or unsafe. Stay cautious with unexpected links or requests.")


def sanitize_message(text: str) -> str:
    """Strip control characters and surrounding whitespace (output is escaped on render)."""
    return _CONTROL_CHARS.sub("", text).strip()


@prediction_bp.post("/predict")
def predict():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("Request body must be JSON.", 400)
    raw = data.get("message")
    if not isinstance(raw, str):
        return error("'message' must be a string.", 400)
    text = sanitize_message(raw)
    if not text:
        return error("Message cannot be empty.", 400)
    max_len = current_app.config["MAX_MESSAGE_LENGTH"]
    if len(text) > max_len:
        return error(f"Message is too long (maximum {max_len} characters).", 413)

    if not classifier.is_ready():
        return error("Model is not trained yet. Run `python -m ml_model.train_model`.", 503)
    try:
        result = classifier.predict(text)
    except Exception:
        current_app.logger.exception("prediction failed")
        return error("Prediction failed.", 500)

    record = Message(user_id=session.get("user_id"), message_text=text,
                     prediction=result["prediction"], confidence_score=result["confidence"])
    try:
        db.session.add(record)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("could not store prediction")
        return error("Could not store the prediction.", 500)

    is_spam = result["is_spam"]
    return jsonify({
        "id": record.id,
        "prediction": result["prediction"],
        "label": "SPAM DETECTED" if is_spam else "NOT SPAM",
        "confidence_score": round(result["confidence"], 4),
        "confidence_percent": round(result["confidence"] * 100, 2),
        "spam_probability": round(result["spam_probability"], 4),
        "ham_probability": round(result["ham_probability"], 4),
        "recommendation": SPAM_ADVICE if is_spam else HAM_NOTE,
        "disclaimer": DISCLAIMER,
        "created_at": record.to_dict()["created_at"],
    }), 200


@prediction_bp.get("/stats/summary")
def summary():
    """Public, aggregate-only counters (no message content)."""
    rows = dict(db.session.query(Message.prediction, func.count(Message.id))
                .group_by(Message.prediction).all())
    spam, ham = int(rows.get("spam", 0)), int(rows.get("ham", 0))
    return jsonify({"total": spam + ham, "spam": spam, "ham": ham}), 200
