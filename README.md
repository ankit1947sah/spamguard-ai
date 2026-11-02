# SpamGuard AI – AI-Based Spam Message Detection System

A full-stack web application that classifies SMS, email or plain-text messages as **SPAM** or **NOT SPAM (ham)** using a locally trained machine-learning model. Built with Flask, scikit-learn, MySQL and Bootstrap 5. No paid APIs or external services are used for predictions.

## Problem statement
Spam and phishing messages waste time and put people at risk of fraud. Rule-based filters are brittle; a model trained on labelled examples generalises to messages it has never seen. SpamGuard AI offers a simple, beginner-friendly interface on top of such a model, keeps a history of every check, and gives an admin a statistics dashboard.

## Objectives
- Classify messages accurately with NLP + machine learning.
- Show the prediction instantly with a confidence score (a model score, **not** a guarantee of safety).
- Store every prediction in MySQL and let users search, filter and delete their history.
- Provide an admin dashboard with totals, a pie chart and daily statistics.
- Validate input, handle errors gracefully and follow secure practices.


## Features
- **Home / detector**: textarea, Detect and Clear buttons, example spam and legitimate messages, live counters, red/green result card with probability bar, safety advice, confidence disclaimer, and a "was this right?" feedback control.
- **History**: per-user list with search, spam / not-spam filter, pagination, single delete and clear-all.
- **Admin dashboard**: totals, spam percentage, recent activity, pie chart, 7-day bar chart, latest model metrics and **CSV upload to retrain** the model.
- **Authentication**: register / login / logout, hashed passwords (scrypt via Werkzeug), login throttling, admin role that cannot be self-assigned.
- **REST API** with JSON, status codes, validation and consistent error bodies.
- **Tests**: 77 automated tests (unit, integration, model, security) with an auto-generated report.


## Technology stack
| Layer | Tools |
|---|---|
| Frontend | HTML5, CSS3, JavaScript, Bootstrap 5, Chart.js |
| Backend | Python, Flask, REST API |
| ML / NLP | scikit-learn, Pandas, NumPy, NLTK (Porter stemmer), TF-IDF, Multinomial Naive Bayes, Logistic Regression, Joblib |
| Database | MySQL (XAMPP / phpMyAdmin), SQLAlchemy ORM, Flask-Migrate (Alembic) |
| Testing | Pytest, Flask test client |

## Machine learning workflow
1. **Dataset**: SMS Spam Collection (`dataset/spam.csv`, 5,572 rows → 5,158 unique messages: 642 spam / 4,516 ham).
2. **Preprocessing** (`ml_model/preprocess.py`): lowercase → URLs / e-mails / long numbers / currency symbols mapped to tokens → punctuation and special characters removed → stop words removed → Porter stemming. Missing and duplicate rows are dropped at load time.
3. **Features**: TF-IDF (unigrams + bigrams, `min_df=2`, sublinear TF).
4. **Models**: Multinomial Naive Bayes and Logistic Regression are both trained on the 80 % training split.
5. **Selection**: the best model is chosen by 5-fold cross-validated F1 on the *training* split only; the 20 % held-out test split is used purely for reporting.
6. **Evaluation**: accuracy, precision, recall, F1, confusion matrix and classification report (spam = positive class).
7. **Persistence**: the winner is saved with Joblib to `ml_model/spam_model.pkl` and the vectorizer to `ml_model/vectorizer.pkl`; full metrics go to `ml_model/metrics.json`.

Results on the held-out test split (1,032 messages, from the run included in this project):

| Model | Accuracy | Precision | Recall | F1 |
|---|---|---|---|---|
| Multinomial Naive Bayes | 0.9845 | 0.9667 | 0.9062 | 0.9355 |
| **Logistic Regression (selected)** | **0.9893** | **0.9680** | **0.9453** | **0.9565** |

Your numbers may differ slightly if you retrain on a different dataset. The SMS Spam Collection is short English SMS text; the model will be less reliable on long e-mails or other languages.

## Database schema
Database: `spam_detection_db` (utf8mb4).

| Table | Columns |
|---|---|
| `users` | id, name, email (unique), password_hash, role (`user`/`admin`), created_at |
| `messages` | id, user_id → users.id (SET NULL), message_text, prediction (`spam`/`ham`), confidence_score (0–1), created_at. Indexes: (user_id, created_at), prediction, created_at |
| `model_logs` | id, model_name, accuracy, precision, recall, f1_score, trained_at |
| `feedback` | id, message_id → messages.id (CASCADE), user_feedback (`correct`/`incorrect`), comments, created_at |

All queries go through the SQLAlchemy ORM (parameterized). Migrations live in `migrations/`; a hand-written script is in `database/setup.sql`.

## Installation (Windows)
Requires Python 3.10+ and [XAMPP](https://www.apachefriends.org/).


1. **Install Python dependencies**
   ```bat
   cd spamguard-ai
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Install and start XAMPP**, then in the XAMPP Control Panel start **Apache** and **MySQL**.

3. **Create the database** – open http://localhost/phpmyadmin → *New* → name `spam_detection_db`, collation `utf8mb4_unicode_ci` → *Create*.
   (Alternatively open the *SQL* tab and paste `database/setup.sql`, which creates the database and all tables.)
4. **Configure `.env`**
   ```bat
   copy .env.example .env
   ```
   Edit `.env`: set a long random `SECRET_KEY` and an `ADMIN_PASSWORD`. XAMPP's default MySQL user is `root` with an empty password, which matches the defaults.
5. **Dataset** – `dataset/spam.csv` is already included (SMS Spam Collection). To use another dataset, see *Dataset instructions* below.
6. **Train the model**
   ```bat
   python -m ml_model.train_model --log-db
   ```
   (`--log-db` also records the metrics in the `model_logs` table; drop it if you only want the `.pkl` files.) A trained model is already included, so this step is optional.
7. **Initialize database tables and the admin account**
   ```bat
   set FLASK_APP=app.py
   flask db upgrade
   flask init-db
   ```
   `flask db upgrade` applies the migration; `flask init-db` creates any missing tables and the admin user from `ADMIN_EMAIL` / `ADMIN_PASSWORD`. (If you imported `setup.sql` in step 3 you only need `flask init-db`; skip `flask db upgrade` to avoid a "table already exists" error, or run `flask db stamp head` first.)
8. **Start the app**
   ```bat
   python app.py
   ```
9. **Open** http://127.0.0.1:5000

The admin logs in with the e-mail and password from `.env`, then opens **Dashboard**. Extra admins: `flask create-admin`.

## Dataset instructions
- Included: `dataset/spam.csv` (columns `v1` = label, `v2` = text, Latin-1 encoded).
- Your own data: any CSV/TSV with a label column (`label`, `v1`, `category`, `class`, `type` …; values `spam`/`ham`) and a text column (`text`, `v2`, `message`, `sms` …), or a header-less two-column file. Then either run `python -m ml_model.train_model --data path\to\file.csv`, or log in as admin and use **Retrain with your own CSV** on the Dashboard (the live model is reloaded automatically).
- Source of the original data: UCI Machine Learning Repository, *SMS Spam Collection*.

## MySQL configuration
`config.py` reads `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` from `.env` and builds `mysql+pymysql://user:password@host:port/db?charset=utf8mb4`. You can instead set one `DATABASE_URL`. If MySQL listens on a different port in XAMPP, update `DB_PORT`.

## API documentation
JSON in / JSON out. Every `POST` / `DELETE` must send the header `X-Requested-With: XMLHttpRequest` (the web UI does this; it is a CSRF safeguard). Authentication uses a secure, HTTP-only session cookie.

| Method & path | Auth | Description |
|---|---|---|
| `POST /api/register` | – | `{name, email, password}` → 201 user. Password ≥ 8 chars with a letter and a digit. 400 invalid, 409 duplicate. |
| `POST /api/login` | – | `{email, password}` → 200 user; 401 invalid; 429 after 5 failures in 5 min. |
| `POST /api/logout`, `GET /api/me` | – / user | End session / current user. |
| `POST /api/predict` | optional | `{message}` (≤ 5000 chars) → `{id, prediction, label, confidence_percent, spam_probability, ham_probability, recommendation, disclaimer}`. Stored with the user id (or NULL if anonymous). 400 / 413 / 503. |
| `GET /api/history` | user | Query: `page`, `per_page` (≤ 50), `filter` = `all`/`spam`/`ham`, `q` (search). Returns `items, page, pages, total`. |
| `GET /api/history/<id>` | user | One of your records (404 otherwise). |
| `DELETE /api/history/<id>` | user | Delete one record. |
| `DELETE /api/history` | user | Clear all of your records. |
| `POST /api/feedback` | optional | `{message_id, user_feedback: "correct"\|"incorrect", comments?}` → 201. |
| `GET /api/dashboard/stats` | admin | Totals, spam %, 7-day daily counts, recent activity, latest model log. |
| `GET /api/health` | – | `{status, database, model}`; 503 if degraded. |
| `GET /api/stats/summary` | – | Aggregate counters for the home page. |
| `POST /api/admin/train` | admin | Multipart CSV upload in field `file`; retrains and reloads the model. |

Errors always look like `{"error": "message"}`.

## Testing
```bat
pytest                      # run everything
pytest --write-report       # also regenerate reports/test_report.md from the real results
```
Test files: `tests/test_model.py` (preprocessing, predictions, unseen messages, held-out metrics), `tests/test_api.py` (REST + integration), `tests/test_database.py` (ORM, constraints, MySQL connectivity), `tests/test_auth.py` (auth + security). The suite uses an in-memory SQLite database, except `TC-DB-09`, which connects to your real MySQL server and is **skipped** automatically if MySQL is not running. See `reports/test_report.md` for the last executed results.

## Screenshots
Add your own screenshots here after running the app locally:

- `static/images/home.png` – detector page
- `static/images/history.png` – history page
- `static/images/dashboard.png` – admin dashboard

## Security notes
Passwords hashed (scrypt); parameterized ORM queries; `LIKE` wildcards escaped in search; input length-limited and control characters stripped; all user text inserted with `textContent` in the browser; HTTP-only + SameSite session cookie; CSRF header check; CSP and other security headers; login throttling; users can only read/delete their own history. For anything beyond local use: set a strong `SECRET_KEY`, serve over HTTPS with `SESSION_COOKIE_SECURE=1`, and run behind a production WSGI server (e.g. waitress on Windows) instead of `python app.py`. The login throttle is in-memory and per-process.

## Future enhancements
Email (`.eml`) parsing, multilingual models, transformer-based classifier, active learning from the stored feedback, password reset by e-mail, rate limiting with Redis, Docker setup, CSV export of history.
