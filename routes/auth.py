"""Authentication: register, logout, current user + access-control decorators."""
import re
from functools import wraps

from flask import Blueprint, jsonify, request, session

from database.db import db
from database.models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/api")

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def error(message: str, status: int):
    return jsonify({"error": message}), status


def get_current_user():
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if user is None:
            session.pop("user_id", None)
            return error("Authentication required.", 401)
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return error("Authentication required.", 401)
        if not user.is_admin:
            return error("Administrator access required.", 403)
        return fn(*args, **kwargs)
    return wrapper


def _validate_password(password: str):
    if not isinstance(password, str) or len(password) < 8:
        return "Password must be at least 8 characters."
    if len(password) > 128:
        return "Password must be at most 128 characters."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Password must contain at least one letter and one number."
    return None


def _start_session(user: User) -> None:
    session.clear()  # prevents session fixation
    session.permanent = True
    session["user_id"] = user.id


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("Request body must be JSON.", 400)
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    if not isinstance(name, str) or not 2 <= len(name.strip()) <= 100:
        return error("Name must be between 2 and 100 characters.", 400)
    if not isinstance(email, str) or len(email) > 255 or not EMAIL_RE.match(email.strip()):
        return error("Please provide a valid email address.", 400)
    problem = _validate_password(password)
    if problem:
        return error(problem, 400)

    email = email.strip().lower()
    if User.query.filter_by(email=email).first():
        return error("An account with this email already exists.", 409)

    user = User(name=name.strip(), email=email, role="user")  # role is never taken from the client
    user.set_password(password)
    try:
        db.session.add(user)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("register failed")
        return error("Could not create account.", 500)
    _start_session(user)
    return jsonify({"message": "Account created.", "user": user.to_dict()}), 201


@auth_bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out."}), 200


@auth_bp.get("/me")
def me():
    user = get_current_user()
    if user is None:
        return error("Authentication required.", 401)
    return jsonify({"user": user.to_dict()}), 200
