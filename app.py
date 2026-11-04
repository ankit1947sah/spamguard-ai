"""SpamGuard AI - Flask application factory, page routes and CLI commands."""
import click
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from werkzeug.exceptions import HTTPException

from config import Config
from database.db import db, migrate
from routes.auth import auth_bp, get_current_user
from routes.dashboard import dashboard_bp
from routes.history import history_bp
from routes.prediction import prediction_bp

CSP = ("default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; "
       "style-src 'self' https://cdn.jsdelivr.net; font-src 'self' https://cdn.jsdelivr.net; "
       "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")


def create_app(config_object=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    migrate.init_app(app, db)
    import database.models  # noqa: F401  (register models for migrations)
    with app.app_context():
        try:
            db.create_all()
        except Exception:
            app.logger.exception("Failed to initialize database tables on startup")

    for bp in (auth_bp, prediction_bp, history_bp, dashboard_bp):
        app.register_blueprint(bp)

    register_hooks(app)
    register_pages(app)
    register_errors(app)
    register_cli(app)
    return app


def register_hooks(app: Flask) -> None:
    @app.before_request
    def require_ajax_header_for_writes():
        # CSRF defence in depth: browsers cannot add a custom header cross-site without CORS approval.
        if (request.path.startswith("/api/") and request.method in ("POST", "PUT", "PATCH", "DELETE")
                and request.headers.get("X-Requested-With") != "XMLHttpRequest"):
            return jsonify({"error": "Missing X-Requested-With header."}), 403

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault("Content-Security-Policy", CSP)
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.context_processor
    def inject_user():
        user = get_current_user()
        return {"current_user": user.to_dict() if user else None}


def register_pages(app: Flask) -> None:
    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/detect")
    def detect():
        return redirect(url_for("index") + "#detect")

    @app.get("/history")
    def history_page():
        return render_template("history.html")

    @app.get("/dashboard")
    def dashboard_page():
        user = get_current_user()
        if user is None:
            return redirect(url_for("register_page", next="/dashboard"))
        if not user.is_admin:
            return render_template("dashboard.html", forbidden=True), 403
        return render_template("dashboard.html", forbidden=False)

    @app.get("/register")
    def register_page():
        if get_current_user():
            return redirect(url_for("index"))
        return render_template("register.html")


def register_errors(app: Flask) -> None:
    @app.errorhandler(HTTPException)
    def http_error(exc):
        if request.path.startswith("/api/"):
            return jsonify({"error": exc.description or exc.name}), exc.code
        return (f"<h1>{exc.code} {exc.name}</h1><p><a href='/'>Back to SpamGuard AI</a></p>", exc.code)

    @app.errorhandler(Exception)
    def unhandled(exc):
        app.logger.exception("Unhandled error")
        db.session.rollback()
        if request.path.startswith("/api/"):
            return jsonify({"error": "Internal server error."}), 500
        return "<h1>500 Internal Server Error</h1><p><a href='/'>Back</a></p>", 500


def register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db():
        """Create tables (if missing) and the admin account from ADMIN_* settings."""
        from database.models import User
        db.create_all()
        click.echo("Tables ready.")
        email = app.config["ADMIN_EMAIL"].lower()
        password = app.config["ADMIN_PASSWORD"]
        if not password:
            click.echo("ADMIN_PASSWORD not set - skipped admin creation (use `flask create-admin`).")
            return
        if User.query.filter_by(email=email).first():
            click.echo(f"Admin {email} already exists.")
            return
        admin = User(name=app.config["ADMIN_NAME"], email=email, role="admin")
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Admin created: {email}")

    @app.cli.command("create-admin")
    @click.option("--name", prompt=True)
    @click.option("--email", prompt=True)
    @click.password_option()
    def create_admin(name, email, password):
        """Create (or promote) an administrator account."""
        from database.models import User
        email = email.strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            user.role = "admin"
            user.set_password(password)
        else:
            user = User(name=name, email=email, role="admin")
            user.set_password(password)
            db.session.add(user)
        db.session.commit()
        click.echo(f"Administrator ready: {email}")


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=app.config.get("DEBUG", False) or
            __import__("os").getenv("FLASK_DEBUG") == "1")
