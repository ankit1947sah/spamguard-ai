"""Database-layer tests (SQLite in-memory for unit tests; real MySQL connectivity test when reachable)."""
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from config import build_database_uri
from database.db import db
from database.models import Feedback, Message, ModelLog, User


def _user(email="a@example.com"):
    u = User(name="A", email=email)
    u.set_password("Passw0rd1")
    db.session.add(u)
    db.session.commit()
    return u


def test_tables_exist(app):
    """TC-DB-01 | All four tables are created | db.create_all() | users, messages, model_logs, feedback exist"""
    assert {"users", "messages", "model_logs", "feedback"} <= set(inspect(db.engine).get_table_names())


def test_user_defaults_and_hash(app):
    """TC-DB-02 | User defaults and password hashing | New user, password 'Passw0rd1' | role='user', created_at set, hash != plain text"""
    u = _user()
    assert u.role == "user" and u.created_at is not None
    assert u.password_hash != "Passw0rd1" and u.check_password("Passw0rd1") and not u.check_password("wrong")


def test_unique_email(app):
    """TC-DB-03 | Email uniqueness constraint | Two users with the same email | IntegrityError on the second insert"""
    _user("dup@example.com")
    dup = User(name="B", email="dup@example.com", password_hash="x")
    db.session.add(dup)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_message_insert_and_query(app):
    """TC-DB-04 | Insert and query a message | Message(user, 'hello', ham, 0.97) | Row is retrievable with the same values"""
    u = _user()
    db.session.add(Message(user_id=u.id, message_text="hello", prediction="ham", confidence_score=0.97))
    db.session.commit()
    m = Message.query.filter_by(user_id=u.id).one()
    assert m.message_text == "hello" and m.prediction == "ham" and abs(m.confidence_score - 0.97) < 1e-6


def test_parameterized_injection_text(app):
    """TC-DB-05 | SQL metacharacters are stored as data | message_text = \"x'); DROP TABLE messages;--\" | Stored verbatim, table still exists"""
    payload = "x'); DROP TABLE messages;--"
    db.session.add(Message(message_text=payload, prediction="spam", confidence_score=0.9))
    db.session.commit()
    assert Message.query.one().message_text == payload
    assert "messages" in inspect(db.engine).get_table_names()


def test_model_log(app):
    """TC-DB-06 | ModelLog insert | accuracy .98, precision .97, recall .95, f1 .96 | Row stored with trained_at timestamp"""
    db.session.add(ModelLog(model_name="LR", accuracy=.98, precision=.97, recall=.95, f1_score=.96))
    db.session.commit()
    assert ModelLog.query.one().trained_at is not None


def test_feedback_relationship_and_cascade(app):
    """TC-DB-07 | Feedback linked to message and cascades on delete | Feedback for a message, then delete the message | Feedback row removed"""
    m = Message(message_text="m", prediction="ham", confidence_score=.9)
    db.session.add(m)
    db.session.commit()
    db.session.add(Feedback(message_id=m.id, user_feedback="correct", comments="ok"))
    db.session.commit()
    assert Feedback.query.count() == 1
    db.session.delete(m)
    db.session.commit()
    assert Feedback.query.count() == 0


def test_declared_indexes_and_fks(app):
    """TC-DB-08 | Foreign keys and indexes are declared | Inspect messages / feedback tables | FKs to users/messages and indexes on prediction, created_at"""
    insp = inspect(db.engine)
    assert insp.get_foreign_keys("messages")[0]["referred_table"] == "users"
    assert insp.get_foreign_keys("feedback")[0]["referred_table"] == "messages"
    idx = {i["name"] for i in insp.get_indexes("messages")}
    assert {"ix_messages_prediction", "ix_messages_created_at", "ix_messages_user_created"} <= idx


def _mysql_engine():
    try:
        eng = create_engine(build_database_uri(), connect_args={"connect_timeout": 3})
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return eng
    except Exception:
        return None


def test_mysql_connectivity(actual):
    """TC-DB-09 | Backend connects to the real MySQL server and the schema exists | DB_* settings from .env | SELECT 1 works and the four tables exist (skipped if MySQL is not running)"""
    if not build_database_uri().startswith("mysql"):
        pytest.skip("DATABASE_URL does not point at MySQL")
    eng = _mysql_engine()
    if eng is None:
        pytest.skip("MySQL server not reachable with current .env settings")
    tables = set(inspect(eng).get_table_names())
    actual(f"connected; tables: {sorted(tables)}")
    assert {"users", "messages", "model_logs", "feedback"} <= tables
