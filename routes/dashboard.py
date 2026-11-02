"""Admin dashboard stats, model (re)training from an uploaded CSV, and the health check."""
import os
import tempfile
from datetime import timedelta

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import func, text

from database.db import db
from database.models import Message, ModelLog, User, iso, utcnow
from ml_model.predict import classifier
from routes.auth import admin_required, error

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api")


@dashboard_bp.get("/health")
def health():
    db_ok = True
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    ready = classifier.is_ready()
    body = {"status": "ok" if (db_ok and ready) else "degraded",
            "database": "connected" if db_ok else "unreachable",
            "model": "available" if ready else "missing"}
    return jsonify(body), 200 if (db_ok and ready) else 503


@dashboard_bp.get("/dashboard/stats")
@admin_required
def stats():
    rows = dict(db.session.query(Message.prediction, func.count(Message.id))
                .group_by(Message.prediction).all())
    spam, ham = int(rows.get("spam", 0)), int(rows.get("ham", 0))
    total = spam + ham

    today = utcnow().date()
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    start = days[0]
    daily = {d.isoformat(): {"spam": 0, "ham": 0} for d in days}
    for day, pred, n in (db.session.query(func.date(Message.created_at), Message.prediction,
                                          func.count(Message.id))
                         .filter(Message.created_at >= start)
                         .group_by(func.date(Message.created_at), Message.prediction).all()):
        key = str(day)
        if key in daily and pred in ("spam", "ham"):
            daily[key][pred] = int(n)

    recent = (Message.query.order_by(Message.created_at.desc(), Message.id.desc()).limit(10).all())
    latest_model = ModelLog.query.order_by(ModelLog.trained_at.desc(), ModelLog.id.desc()).first()
    return jsonify({
        "total_messages": total,
        "total_spam": spam,
        "total_ham": ham,
        "spam_percentage": round(spam / total * 100, 2) if total else 0.0,
        "total_users": User.query.count(),
        "daily": [{"date": d, **v} for d, v in daily.items()],
        "recent": [{**m.to_dict(), "message_text": m.message_text[:120]} for m in recent],
        "latest_model": latest_model.to_dict() if latest_model else None,
    }), 200


@dashboard_bp.post("/admin/train")
@admin_required
def train_from_upload():
    """Retrain from an uploaded CSV (label + text columns), reload the live model, log metrics."""
    from ml_model.train_model import load_dataset, train

    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return error("Attach a CSV file in the 'file' field.", 400)
    if not upload.filename.lower().endswith((".csv", ".tsv")):
        return error("Only .csv or .tsv files are accepted.", 400)

    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    try:
        upload.save(path)
        try:
            df = load_dataset(path)
        except Exception as exc:
            return error(f"Invalid dataset: {exc}", 400)
        summary = train(df, verbose=False)
    except Exception:
        current_app.logger.exception("training failed")
        return error("Training failed.", 500)
    finally:
        os.path.exists(path) and os.remove(path)

    classifier.reload()
    try:
        for name, res in summary["results"].items():
            label = name + (" (selected)" if name == summary["selected_model"] else "")
            db.session.add(ModelLog(model_name=label, accuracy=res["accuracy"], precision=res["precision"],
                                    recall=res["recall"], f1_score=res["f1_score"]))
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("could not log model metrics")
    return jsonify({"message": "Model retrained and reloaded.",
                    "selected_model": summary["selected_model"],
                    "dataset_size": summary["dataset_size"],
                    "metrics": {k: {m: v[m] for m in ("accuracy", "precision", "recall", "f1_score")}
                                for k, v in summary["results"].items()}}), 200
