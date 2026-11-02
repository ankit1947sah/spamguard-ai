"""Shared fixtures + a plugin that writes reports/test_report.md from REAL test outcomes.

Each test docstring is:  "TC-ID | Scenario | Input | Expected result".
Tests may call the `actual` fixture to record what they observed; otherwise the report
shows the assertion failure text (on fail) or a generic note (on pass).
Run with `pytest --write-report` to (re)generate reports/test_report.md.
"""
import os
from datetime import datetime

import pytest

from app import create_app
from config import TestConfig
from database.db import db
from database.models import User

AJAX = {"X-Requested-With": "XMLHttpRequest"}
REPORT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "reports", "test_report.md")
_results = []


def pytest_addoption(parser):
    parser.addoption("--write-report", action="store_true", help="write reports/test_report.md")


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    c = app.test_client()
    c.environ_base["REMOTE_ADDR"] = "127.0.0.1"
    return c


@pytest.fixture()
def actual(request):
    def record(text):
        request.node._actual = str(text)
    return record


def post(client, url, payload=None, **kw):
    return client.post(url, json=payload if payload is not None else {}, headers=AJAX, **kw)


def delete(client, url):
    return client.delete(url, headers=AJAX)


def register(client, email="user@example.com", password="Passw0rd!x", name="Test User"):
    return post(client, "/api/register", {"name": name, "email": email, "password": password})


def login(client, email="user@example.com", password="Passw0rd!x"):
    return post(client, "/api/login", {"email": email, "password": password})


@pytest.fixture()
def user_client(client):
    assert register(client).status_code == 201
    return client


@pytest.fixture()
def admin_client(app):
    admin = User(name="Admin", email="admin@example.com", role="admin")
    admin.set_password("AdminPass123")
    db.session.add(admin)
    db.session.commit()
    c = app.test_client()
    assert login(c, "admin@example.com", "AdminPass123").status_code == 200
    return c


# ---------- report plugin ----------
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    final = (rep.when == "call") or (rep.when == "setup" and rep.outcome in ("skipped", "failed"))
    if not final:
        return
    doc = (item.function.__doc__ or "").strip()
    parts = [p.strip() for p in doc.split("|")]
    if len(parts) < 4:
        parts += [""] * (4 - len(parts))
    tc_id, scenario, inp, expected = parts[0], parts[1], parts[2], "|".join(parts[3:]).strip()
    if rep.outcome == "passed":
        status, act = "PASS", getattr(item, "_actual", "Matched expected result")
    elif rep.outcome == "skipped":
        status = "SKIPPED"
        act = str(rep.longrepr[-1]) if isinstance(rep.longrepr, tuple) else "skipped"
    else:
        status = "FAIL"
        txt = rep.longreprtext.strip().splitlines()
        act = getattr(item, "_actual", "") or (txt[-1] if txt else "failed")
    _results.append((tc_id or item.name, scenario or item.name, inp, expected,
                     act.replace("|", "/").replace("\n", " ")[:200], status))


def pytest_sessionfinish(session, exitstatus):
    if not session.config.getoption("--write-report") or not _results:
        return
    counts = {s: sum(1 for r in _results if r[5] == s) for s in ("PASS", "FAIL", "SKIPPED")}
    lines = [
        "# SpamGuard AI - Test Report", "",
        f"Generated automatically by `pytest --write-report` on {datetime.now():%Y-%m-%d %H:%M:%S}.",
        "Every row below comes from a test that was actually executed in that run.", "",
        f"**Total: {len(_results)}  |  Passed: {counts['PASS']}  |  Failed: {counts['FAIL']}  |  Skipped: {counts['SKIPPED']}**", "",
        "| Test case ID | Test scenario | Input | Expected result | Actual result | Status |",
        "|---|---|---|---|---|---|",
    ]
    for r in sorted(_results, key=lambda x: x[0]):
        lines.append("| " + " | ".join(c.replace("|", "/") for c in r) + " |")
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
