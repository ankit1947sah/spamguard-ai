"""History endpoints (per-user) and prediction feedback."""
from flask import Blueprint, current_app, jsonify, request, session

from database.db import db
from database.models import Feedback, Message
from routes.auth import error, get_current_user, login_required

history_bp = Blueprint("history", __name__, url_prefix="/api")


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _own(message_id: int):
    user = get_current_user()
    msg = db.session.get(Message, message_id)
    if msg is None or msg.user_id != user.id:
        return None  # 404 for both "missing" and "not yours" so ids can't be probed
    return msg


@history_bp.get("/history")
@login_required
def list_history():
    user = get_current_user()
    try:
        page = max(int(request.args.get("page", 1)), 1)
        per_page = min(max(int(request.args.get("per_page", 10)), 1), 50)
    except ValueError:
        return error("'page' and 'per_page' must be integers.", 400)
    flt = (request.args.get("filter") or "all").lower()
    if flt not in ("all", "spam", "ham"):
        return error("'filter' must be one of: all, spam, ham.", 400)
    q = (request.args.get("q") or "").strip()

    query = Message.query.filter(Message.user_id == user.id)
    if flt != "all":
        query = query.filter(Message.prediction == flt)
    if q:
        query = query.filter(Message.message_text.ilike(f"%{_escape_like(q[:200])}%", escape="\\"))
    pagination = query.order_by(Message.created_at.desc(), Message.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False)
    return jsonify({
        "items": [m.to_dict() for m in pagination.items],
        "page": pagination.page,
        "per_page": per_page,
        "pages": pagination.pages,
        "total": pagination.total,
    }), 200


@history_bp.get("/history/<int:message_id>")
@login_required
def get_history_item(message_id):
    msg = _own(message_id)
    if msg is None:
        return error("Record not found.", 404)
    return jsonify(msg.to_dict()), 200


@history_bp.delete("/history/<int:message_id>")
@login_required
def delete_history_item(message_id):
    msg = _own(message_id)
    if msg is None:
        return error("Record not found.", 404)
    try:
        db.session.delete(msg)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("delete failed")
        return error("Could not delete the record.", 500)
    return jsonify({"message": "Record deleted."}), 200


@history_bp.delete("/history")
@login_required
def clear_history():
    user = get_current_user()
    try:
        ids = [i for (i,) in db.session.query(Message.id).filter(Message.user_id == user.id).all()]
        for msg in Message.query.filter(Message.id.in_(ids)).all():
            db.session.delete(msg)  # ORM delete so feedback rows cascade on every backend
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("clear failed")
        return error("Could not clear history.", 500)
    return jsonify({"message": "History cleared.", "deleted": len(ids)}), 200


@history_bp.post("/feedback")
def submit_feedback():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("Request body must be JSON.", 400)
    message_id = data.get("message_id")
    verdict = data.get("user_feedback")
    comments = data.get("comments")
    if not isinstance(message_id, int) or isinstance(message_id, bool):
        return error("'message_id' must be an integer.", 400)
    if verdict not in ("correct", "incorrect"):
        return error("'user_feedback' must be 'correct' or 'incorrect'.", 400)
    if comments is not None:
        if not isinstance(comments, str) or len(comments) > 1000:
            return error("'comments' must be text of at most 1000 characters.", 400)
        comments = comments.strip() or None

    msg = db.session.get(Message, message_id)
    uid = session.get("user_id")
    # Anonymous predictions (user_id NULL) may receive feedback from anyone; owned ones only from the owner.
    if msg is None or (msg.user_id is not None and msg.user_id != uid):
        return error("Message not found.", 404)
    fb = Feedback(message_id=msg.id, user_feedback=verdict, comments=comments)
    try:
        db.session.add(fb)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("feedback failed")
        return error("Could not save feedback.", 500)
    return jsonify({"message": "Thank you for your feedback.", "feedback": fb.to_dict()}), 201
