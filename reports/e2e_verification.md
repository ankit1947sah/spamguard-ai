# End-to-end verification (manual run, real MySQL)

Run on 2026-11-02 in the build sandbox against a real **MariaDB 10.11** server (MySQL-compatible, root with empty password, like XAMPP), using `python app.py` and `curl`. This is a record of what was actually executed; it is separate from the automated `test_report.md`.

| Step | Result |
|---|---|
| `flask db migrate` / `flask db upgrade` on MariaDB | Initial migration generated and applied; 4 tables + `alembic_version`; FKs and indexes created |
| `flask init-db` | Admin account created, password stored as scrypt hash |
| `GET /api/health` | database connected, model available |
| `GET /`, `/login`, `/register`, `/history` | 200; `/dashboard` and `/detect` redirect (302) when logged out |
| Register + 2 predictions (prize-claim text, lunch text) | `SPAM DETECTED 99.77%` and `NOT SPAM 99.34%`, rows written to `messages` |
| Stop and restart the server (twice), log in again | History still returned both records (persistence verified) |
| Admin login, `GET /api/dashboard/stats` | totals 2 / spam 1 / ham 1 / 50 %, latest model log shown |
| Dashboard page as admin / as normal user / anonymous API history | 200 / 403 / 401 |
| Feedback on a message, then delete that message | Feedback row removed by the database cascade (count = 0) |

Not verified here: the pages were not opened in a graphical browser (the sandbox cannot load the Bootstrap / Chart.js CDN files), so the visual layout, charts and responsive behaviour have not been checked on screen. The front-end JavaScript is covered only by the API calls above and by markup/wiring tests.
