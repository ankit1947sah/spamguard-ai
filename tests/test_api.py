"""REST API + integration tests (frontend pages <-> backend <-> model <-> database)."""
import io
import os
import re

import pytest

from conftest import AJAX, delete, post, register, login
from database.db import db
from database.models import Feedback, Message
from ml_model.predict import classifier

SPAM = "WINNER!! You have won a free prize. Call 09061701461 now to claim your reward, valid 12 hours only!"
HAM = "Hey, are we still meeting for lunch tomorrow? Let me know what time works for you."

needs_model = pytest.mark.skipif(not classifier.is_ready(), reason="trained model not found")


def test_health(client, actual):
    """TC-API-01 | Health check | GET /api/health | 200 with database connected and model available"""
    r = client.get("/api/health")
    actual(r.get_json())
    assert r.status_code == 200 and r.get_json()["database"] == "connected"


@needs_model
def test_predict_spam(client, actual):
    """TC-API-02 | Predict a spam message | Prize-claim text | 200, SPAM DETECTED, confidence + probabilities + disclaimer"""
    r = post(client, "/api/predict", {"message": SPAM})
    j = r.get_json()
    actual(f"{j['label']} ({j['confidence_percent']}%)")
    assert r.status_code == 200 and j["prediction"] == "spam" and j["label"] == "SPAM DETECTED"
    assert abs(j["spam_probability"] + j["ham_probability"] - 1) < 1e-3
    assert "not a guarantee" in j["disclaimer"]


@needs_model
def test_predict_ham(client, actual):
    """TC-API-03 | Predict a legitimate message | Lunch-plan text | 200, NOT SPAM"""
    j = post(client, "/api/predict", {"message": HAM}).get_json()
    actual(f"{j['label']} ({j['confidence_percent']}%)")
    assert j["prediction"] == "ham" and j["label"] == "NOT SPAM"


@pytest.mark.parametrize("payload,code", [
    ({"message": ""}, 400), ({"message": "    "}, 400), ({}, 400), ({"message": 123}, 400),
    ({"message": None}, 400), ({"message": ["a"]}, 400), ({"message": "x" * 5001}, 413),
])
def test_predict_validation(client, payload, code):
    """TC-API-04 | Predict input validation | empty, whitespace, missing, non-string, null, list, 5001 chars | 400 (413 for too long)"""
    assert post(client, "/api/predict", payload).status_code == code


def test_predict_requires_json(client):
    """TC-API-05 | Predict rejects non-JSON bodies | text/plain body | 400"""
    r = client.post("/api/predict", data="hello", headers={**AJAX, "Content-Type": "text/plain"})
    assert r.status_code == 400


@needs_model
def test_predict_control_chars_sanitized(client):
    """TC-SEC-08 | Control characters are stripped from input | 'free\\x00 prize\\x07 now' | Stored text has no control characters"""
    j = post(client, "/api/predict", {"message": "free\x00 prize\x07 now"}).get_json()
    assert Message.query.get(j["id"]).message_text == "free prize now"


@needs_model
def test_prediction_stored_and_history(client, actual):
    """TC-INT-01 | Prediction is stored and retrievable (backend -> model -> database -> history) | Logged-in user predicts 2 messages | History lists both, newest first, with confidence and timestamp"""
    register(client)
    post(client, "/api/predict", {"message": SPAM})
    post(client, "/api/predict", {"message": HAM})
    j = client.get("/api/history").get_json()
    actual(f"total={j['total']}, order={[i['prediction'] for i in j['items']]}")
    assert j["total"] == 2 and j["items"][0]["prediction"] == "ham"
    assert {"message_text", "prediction", "confidence_score", "created_at"} <= set(j["items"][0])


@needs_model
def test_anonymous_prediction_is_stored(client):
    """TC-INT-02 | Anonymous predictions are stored without a user | Predict while logged out | Message row with user_id NULL, counted in summary"""
    post(client, "/api/predict", {"message": SPAM})
    assert Message.query.one().user_id is None
    assert client.get("/api/stats/summary").get_json()["total"] == 1


@needs_model
def test_history_isolated_between_users(app, client):
    """TC-SEC-09 | Users can only see and delete their own history | User A creates a record; user B reads/deletes it | B gets 404 and a different list"""
    register(client, "a@example.com")
    rid = post(client, "/api/predict", {"message": SPAM}).get_json()["id"]
    b = app.test_client()
    register(b, "b@example.com")
    assert b.get("/api/history").get_json()["total"] == 0
    assert b.get(f"/api/history/{rid}").status_code == 404
    assert delete(b, f"/api/history/{rid}").status_code == 404
    assert client.get(f"/api/history/{rid}").status_code == 200


@needs_model
def test_history_filter_search_pagination(client, actual):
    """TC-API-06 | History filter, search and pagination | 12 records (6 spam, 6 ham); filter=spam; q='lunch'; per_page=5 | Correct counts and page math"""
    register(client)
    for i in range(6):
        post(client, "/api/predict", {"message": f"{SPAM} #{i}"})
        post(client, "/api/predict", {"message": f"{HAM} (v{i})"})
    assert client.get("/api/history?filter=spam&per_page=50").get_json()["total"] == 6
    assert client.get("/api/history?filter=ham&per_page=50").get_json()["total"] == 6
    assert client.get("/api/history?q=lunch&per_page=50").get_json()["total"] == 6
    p = client.get("/api/history?per_page=5&page=3").get_json()
    actual(f"pages={p['pages']}, items on page 3={len(p['items'])}")
    assert p["pages"] == 3 and len(p["items"]) == 2


def test_history_bad_params(user_client):
    """TC-API-07 | History rejects bad query params | page=abc, filter=bogus | 400"""
    assert user_client.get("/api/history?page=abc").status_code == 400
    assert user_client.get("/api/history?filter=bogus").status_code == 400


@needs_model
def test_search_sql_injection_and_wildcards(client, actual):
    """TC-SEC-10 | Search term with SQL / LIKE wildcards | q=\"' OR 1=1 --\" and q='%' | No SQL error; wildcard treated literally (0 matches)"""
    register(client)
    post(client, "/api/predict", {"message": HAM})
    a = client.get("/api/history", query_string={"q": "' OR 1=1 --"})
    b = client.get("/api/history", query_string={"q": "%"})
    actual(f"inj total={a.get_json()['total']}, '%' total={b.get_json()['total']}")
    assert a.status_code == 200 and a.get_json()["total"] == 0
    assert b.status_code == 200 and b.get_json()["total"] == 0


@needs_model
def test_delete_one_and_clear(client):
    """TC-API-08 | Delete a record and clear history | 3 records; delete one; clear all | 200s, then empty history; deleting twice gives 404"""
    register(client)
    ids = [post(client, "/api/predict", {"message": f"{HAM} {i}"}).get_json()["id"] for i in range(3)]
    assert delete(client, f"/api/history/{ids[0]}").status_code == 200
    assert delete(client, f"/api/history/{ids[0]}").status_code == 404
    assert client.get("/api/history").get_json()["total"] == 2
    assert delete(client, "/api/history").get_json()["deleted"] == 2
    assert client.get("/api/history").get_json()["total"] == 0


@needs_model
def test_feedback(client, actual):
    """TC-API-09 | Submit feedback | correct / incorrect with comment; invalid verdict; unknown message | 201 for valid, 400 invalid verdict, 404 unknown id"""
    mid = post(client, "/api/predict", {"message": SPAM}).get_json()["id"]
    ok = post(client, "/api/feedback", {"message_id": mid, "user_feedback": "incorrect", "comments": "hmm"})
    bad = post(client, "/api/feedback", {"message_id": mid, "user_feedback": "maybe"})
    missing = post(client, "/api/feedback", {"message_id": 99999, "user_feedback": "correct"})
    actual(f"{ok.status_code}/{bad.status_code}/{missing.status_code}")
    assert (ok.status_code, bad.status_code, missing.status_code) == (201, 400, 404)
    assert Feedback.query.count() == 1


@needs_model
def test_feedback_on_other_users_message(app, client):
    """TC-SEC-11 | Feedback on another user's message is refused | B submits feedback for A's message | 404"""
    register(client, "a@example.com")
    mid = post(client, "/api/predict", {"message": SPAM}).get_json()["id"]
    b = app.test_client()
    register(b, "b@example.com")
    assert post(b, "/api/feedback", {"message_id": mid, "user_feedback": "correct"}).status_code == 404


@needs_model
def test_dashboard_stats_values(app, client, admin_client, actual):
    """TC-API-10 | Admin stats are computed from stored data | 2 spam + 1 ham predictions | total 3, spam 2, ham 1, spam% 66.67, 7 daily buckets, recent list"""
    for m in (SPAM, SPAM + " again", HAM):
        post(client, "/api/predict", {"message": m})
    j = admin_client.get("/api/dashboard/stats").get_json()
    actual({k: j[k] for k in ("total_messages", "total_spam", "total_ham", "spam_percentage")})
    assert (j["total_messages"], j["total_spam"], j["total_ham"]) == (3, 2, 1)
    assert j["spam_percentage"] == 66.67 and len(j["daily"]) == 7 and len(j["recent"]) == 3
    assert sum(d["spam"] + d["ham"] for d in j["daily"]) == 3


def test_admin_train_upload(admin_client, tmp_path, monkeypatch, actual):
    """TC-API-11 | Admin retrains from an uploaded CSV (written to a temp location) | Small synthetic CSV; also a bad file | 200 with metrics for valid CSV, 400 for invalid"""
    import ml_model.train_model as tm
    monkeypatch.setattr(tm, "MODEL_PATH", str(tmp_path / "m.pkl"))
    monkeypatch.setattr(tm, "VECTORIZER_PATH", str(tmp_path / "v.pkl"))
    monkeypatch.setattr(tm, "METRICS_PATH", str(tmp_path / "metrics.json"))
    monkeypatch.setattr(tm.train, "__defaults__", (str(tmp_path / "m.pkl"), str(tmp_path / "v.pkl"),
                                                   str(tmp_path / "metrics.json"), True))
    monkeypatch.setattr(classifier, "reload", lambda: None)
    spam_words = ["win", "free", "prize", "claim", "cash", "offer", "urgent", "bonus"]
    ham_words = ["lunch", "meeting", "tomorrow", "homework", "dinner", "coffee", "weekend", "project"]
    rows = ["label,text"]
    for i in range(60):
        rows.append(f"spam,{spam_words[i % 8]} {spam_words[(i + 3) % 8]} now call {i} {spam_words[(i + 5) % 8]} reward")
        rows.append(f"ham,see you at {ham_words[i % 8]} {ham_words[(i + 2) % 8]} {i} {ham_words[(i + 4) % 8]} later")
    data = {"file": (io.BytesIO("\n".join(rows).encode()), "train.csv")}
    r = admin_client.post("/api/admin/train", data=data, headers=AJAX, content_type="multipart/form-data")
    actual(f"{r.status_code} {r.get_json().get('selected_model') or r.get_json()}")
    assert r.status_code == 200 and "metrics" in r.get_json()
    bad = {"file": (io.BytesIO(b"nonsense"), "bad.csv")}
    r2 = admin_client.post("/api/admin/train", data=bad, headers=AJAX, content_type="multipart/form-data")
    assert r2.status_code == 400
    r3 = admin_client.post("/api/admin/train", data={"file": (io.BytesIO(b"x"), "x.exe")},
                           headers=AJAX, content_type="multipart/form-data")
    assert r3.status_code == 400


def test_json_errors(client, user_client):
    """TC-API-12 | Unknown routes and wrong methods return JSON errors | GET /api/nope, PUT /api/predict | 404 and 405 JSON bodies"""
    r = client.get("/api/nope")
    assert r.status_code == 404 and "error" in r.get_json()
    r = client.put("/api/predict", headers=AJAX, json={})
    assert r.status_code == 405 and "error" in r.get_json()


@pytest.mark.parametrize("path,needle", [
    ("/", "Detect Spam Messages Instantly"),
    ("/login", "loginForm"), ("/register", "registerForm"),
    ("/history", "Detection History"),
])
def test_pages_render(client, path, needle):
    """TC-INT-03 | Frontend pages render with their forms/headings | GET /, /login, /register, /history | 200 and expected markup present"""
    r = client.get(path)
    assert r.status_code == 200 and needle in r.get_data(as_text=True)


def test_frontend_wiring(client):
    """TC-INT-04 | Frontend script targets every API endpoint the UI uses | Read static/js/script.js | References predict, history, login, register, logout, feedback, stats, train endpoints"""
    js = client.get("/static/js/script.js").get_data(as_text=True)
    for ep in ("/api/predict", "/api/history", "/api/login", "/api/register", "/api/logout",
               "/api/feedback", "/api/stats/summary", "/api/dashboard/stats", "/api/admin/train"):
        assert ep in js, ep
    html = client.get("/").get_data(as_text=True)
    for element_id in ("message", "detectBtn", "clearBtn", "resultCard", "statTotal", "statSpam", "statHam"):
        assert f'id="{element_id}"' in html, element_id
    assert len(re.findall(r'class="[^"]*\bexample\b', html)) >= 6


@needs_model
def test_xss_payload_not_rendered_raw(client):
    """TC-SEC-12 | XSS payload is stored as text and never injected as markup | message '<script>alert(1)</script> free prize' | Pages don't contain the raw payload; API returns it as JSON data"""
    register(client)
    post(client, "/api/predict", {"message": "<script>alert(1)</script> free prize call now"})
    for page in ("/", "/history"):
        assert "<script>alert(1)</script>" not in client.get(page).get_data(as_text=True)
    item = client.get("/api/history").get_json()["items"][0]
    assert "<script>" in item["message_text"]  # kept verbatim; script.js renders via textContent
    assert "textContent" in client.get("/static/js/script.js").get_data(as_text=True)


@needs_model
def test_persistence_across_app_restart(tmp_path, actual):
    """TC-INT-05 | History persists after the application restarts | Store a prediction, build a NEW app instance on the same database file | Record still present"""
    from app import create_app
    from config import TestConfig

    class FileConfig(TestConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'persist.db'}"

    app1 = create_app(FileConfig)
    with app1.app_context():
        db.create_all()
        c = app1.test_client()
        register(c)
        post(c, "/api/predict", {"message": SPAM})
        db.session.remove()
    app2 = create_app(FileConfig)  # "restart"
    with app2.app_context():
        c2 = app2.test_client()
        assert login(c2).status_code == 200
        total = c2.get("/api/history").get_json()["total"]
        actual(f"records after restart: {total}")
        assert total == 1
        db.session.remove()
        db.drop_all()
