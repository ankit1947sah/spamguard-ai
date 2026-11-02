"""Authentication and security tests."""
import pytest

from conftest import AJAX, delete, login, post, register
from database.db import db
from database.models import User


def test_register_success(client, actual):
    """TC-AUTH-01 | Register a new user | valid name, email, password | 201, role 'user', session started"""
    r = register(client)
    actual(f"{r.status_code} {r.get_json()['user']}")
    assert r.status_code == 201 and r.get_json()["user"]["role"] == "user"
    assert client.get("/api/me").status_code == 200


@pytest.mark.parametrize("payload", [
    {"name": "A", "email": "a@example.com", "password": "Passw0rd1"},
    {"name": "Valid", "email": "not-an-email", "password": "Passw0rd1"},
    {"name": "Valid", "email": "a@example.com", "password": "short1"},
    {"name": "Valid", "email": "a@example.com", "password": "onlyletters"},
    {"name": "Valid", "email": "a@example.com", "password": "12345678"},
    {"name": 5, "email": "a@example.com", "password": "Passw0rd1"},
])
def test_register_validation(client, payload):
    """TC-AUTH-02 | Registration input validation | bad name / email / weak passwords | 400 with an error message"""
    r = post(client, "/api/register", payload)
    assert r.status_code == 400 and "error" in r.get_json()


def test_register_duplicate(client):
    """TC-AUTH-03 | Duplicate email is rejected | Same email twice (different case) | 409"""
    register(client, "dup@example.com")
    assert register(client, "DUP@example.com").status_code == 409


def test_register_cannot_choose_role(client):
    """TC-AUTH-04 | Client cannot self-assign admin role | Register with role='admin' in body | Created account has role 'user'"""
    r = post(client, "/api/register", {"name": "Evil", "email": "e@example.com",
                                      "password": "Passw0rd1", "role": "admin"})
    assert r.status_code == 201 and r.get_json()["user"]["role"] == "user"


def test_password_is_hashed(client, app, actual):
    """TC-SEC-01 | Passwords are never stored in plain text | Register with 'Passw0rd!x' | password_hash differs from the password and is a salted hash"""
    register(client)
    u = User.query.filter_by(email="user@example.com").one()
    actual(u.password_hash[:20] + "...")
    assert u.password_hash != "Passw0rd!x" and "Passw0rd!x" not in u.password_hash
    assert ":" in u.password_hash or u.password_hash.startswith("$")


def test_login_logout_flow(client):
    """TC-AUTH-05 | Login and logout | Valid credentials, then logout | Login 200 with session; /api/me 401 after logout"""
    register(client)
    post(client, "/api/logout")
    assert client.get("/api/me").status_code == 401
    assert login(client).status_code == 200
    assert client.get("/api/me").status_code == 200
    assert post(client, "/api/logout").status_code == 200
    assert client.get("/api/me").status_code == 401


def test_login_invalid(client):
    """TC-AUTH-06 | Wrong password and unknown email give the same error | Bad credentials | 401 with identical message (no user enumeration)"""
    register(client)
    a = login(client, password="WrongPass1")
    b = login(client, email="nobody@example.com")
    assert a.status_code == b.status_code == 401
    assert a.get_json() == b.get_json()


def test_login_lockout(client, actual):
    """TC-SEC-02 | Brute-force throttling | 5 wrong passwords then a correct one | 429 Too Many Requests"""
    register(client)
    for _ in range(5):
        assert login(client, password="WrongPass1").status_code == 401
    r = login(client)
    actual(r.status_code)
    assert r.status_code == 429


def test_login_missing_fields(client):
    """TC-AUTH-07 | Login with missing/invalid fields | {} and non-string values | 400"""
    assert post(client, "/api/login", {}).status_code == 400
    assert post(client, "/api/login", {"email": 1, "password": 2}).status_code == 400


def test_protected_endpoints_require_login(client, actual):
    """TC-SEC-03 | Unauthorised access to protected APIs | History, delete, stats without logging in | 401 for each"""
    codes = [client.get("/api/history").status_code, client.get("/api/history/1").status_code,
             delete(client, "/api/history/1").status_code, delete(client, "/api/history").status_code,
             client.get("/api/dashboard/stats").status_code]
    actual(codes)
    assert codes == [401] * 5


def test_admin_only_endpoints(user_client, actual):
    """TC-SEC-04 | Normal user cannot access admin APIs | Logged-in non-admin calls /api/dashboard/stats and /api/admin/train | 403"""
    a = user_client.get("/api/dashboard/stats").status_code
    b = user_client.post("/api/admin/train", headers=AJAX).status_code
    actual(f"stats={a}, train={b}")
    assert a == 403 and b == 403


def test_admin_access(admin_client):
    """TC-AUTH-08 | Admin can read dashboard stats | Logged-in admin | 200 with totals"""
    r = admin_client.get("/api/dashboard/stats")
    assert r.status_code == 200 and "total_messages" in r.get_json()


def test_dashboard_page_access(client, user_client, admin_client):
    """TC-AUTH-09 | Dashboard page access control | Anonymous, user, admin | Redirect to login (302), 403 page, 200"""
    anon = client.application.test_client()
    assert anon.get("/dashboard").status_code == 302
    assert user_client.get("/dashboard").status_code == 403
    assert admin_client.get("/dashboard").status_code == 200


def test_sql_injection_login(client, actual):
    """TC-SEC-05 | SQL injection in login | email=\"' OR '1'='1\" password=\"' OR '1'='1\" | Rejected (400/401), no session"""
    register(client)
    post(client, "/api/logout")  # start from a logged-out state
    r = post(client, "/api/login", {"email": "' OR '1'='1", "password": "' OR '1'='1"})
    actual(r.status_code)
    assert r.status_code in (400, 401)
    assert r.get_json().get("user") is None
    assert client.get("/api/me").status_code == 401  # no session was created


def test_csrf_header_required(client):
    """TC-SEC-06 | State-changing API calls need the X-Requested-With header | POST /api/predict without the header | 403"""
    r = client.post("/api/predict", json={"message": "hello"})
    assert r.status_code == 403


def test_cookie_flags_and_headers(client, actual):
    """TC-SEC-07 | Session cookie flags and security headers | Register, inspect response | HttpOnly + SameSite cookie, nosniff, X-Frame-Options, CSP"""
    r = register(client)
    cookie = r.headers.get("Set-Cookie", "")
    actual(cookie.split(";")[1:3])
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in r.headers


def test_session_user_deleted(client):
    """TC-AUTH-10 | Stale session for a deleted user is rejected | Delete the user row while the session cookie remains | 401"""
    register(client)
    db.session.delete(User.query.one())
    db.session.commit()
    assert client.get("/api/history").status_code == 401
