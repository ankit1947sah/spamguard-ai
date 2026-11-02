# SpamGuard AI - Test Report

Generated automatically by `pytest --write-report` on 2026-11-03 00:21:18.
Every row below comes from a test that was actually executed in that run.

**Total: 46  |  Passed: 46  |  Failed: 0  |  Skipped: 0**

| Test case ID | Test scenario | Input | Expected result | Actual result | Status |
|---|---|---|---|---|---|
| TC-API-01 | Health check | GET /api/health | 200 with database connected and model available | {'database': 'connected', 'model': 'available', 'status': 'ok'} | PASS |
| TC-API-02 | Predict a spam message | Prize-claim text | 200, SPAM DETECTED, confidence + probabilities + disclaimer | SPAM DETECTED (99.72%) | PASS |
| TC-API-03 | Predict a legitimate message | Lunch-plan text | 200, NOT SPAM | NOT SPAM (99.85%) | PASS |
| TC-API-04 | Predict input validation | empty, whitespace, missing, non-string, null, list, 5001 chars | 400 (413 for too long) | Matched expected result | PASS |
| TC-API-04 | Predict input validation | empty, whitespace, missing, non-string, null, list, 5001 chars | 400 (413 for too long) | Matched expected result | PASS |
| TC-API-04 | Predict input validation | empty, whitespace, missing, non-string, null, list, 5001 chars | 400 (413 for too long) | Matched expected result | PASS |
| TC-API-04 | Predict input validation | empty, whitespace, missing, non-string, null, list, 5001 chars | 400 (413 for too long) | Matched expected result | PASS |
| TC-API-04 | Predict input validation | empty, whitespace, missing, non-string, null, list, 5001 chars | 400 (413 for too long) | Matched expected result | PASS |
| TC-API-04 | Predict input validation | empty, whitespace, missing, non-string, null, list, 5001 chars | 400 (413 for too long) | Matched expected result | PASS |
| TC-API-04 | Predict input validation | empty, whitespace, missing, non-string, null, list, 5001 chars | 400 (413 for too long) | Matched expected result | PASS |
| TC-API-05 | Predict rejects non-JSON bodies | text/plain body | 400 | Matched expected result | PASS |
| TC-API-06 | History filter, search and pagination | 12 records (6 spam, 6 ham); filter=spam; q='lunch'; per_page=5 | Correct counts and page math | pages=3, items on page 3=2 | PASS |
| TC-API-07 | History rejects bad query params | page=abc, filter=bogus | 400 | Matched expected result | PASS |
| TC-API-08 | Delete a record and clear history | 3 records; delete one; clear all | 200s, then empty history; deleting twice gives 404 | Matched expected result | PASS |
| TC-API-09 | Submit feedback | correct / incorrect with comment; invalid verdict; unknown message | 201 for valid, 400 invalid verdict, 404 unknown id | 201/400/404 | PASS |
| TC-API-10 | Admin stats are computed from stored data | 2 spam + 1 ham predictions | total 3, spam 2, ham 1, spam% 66.67, 7 daily buckets, recent list | {'total_messages': 3, 'total_spam': 2, 'total_ham': 1, 'spam_percentage': 66.67} | PASS |
| TC-API-11 | Admin retrains from an uploaded CSV (written to a temp location) | Small synthetic CSV; also a bad file | 200 with metrics for valid CSV, 400 for invalid | 200 Multinomial Naive Bayes | PASS |
| TC-API-12 | Unknown routes and wrong methods return JSON errors | GET /api/nope, PUT /api/predict | 404 and 405 JSON bodies | Matched expected result | PASS |
| TC-INT-01 | Prediction is stored and retrievable (backend -> model -> database -> history) | Logged-in user predicts 2 messages | History lists both, newest first, with confidence and timestamp | total=2, order=['ham', 'spam'] | PASS |
| TC-INT-02 | Anonymous predictions are stored without a user | Predict while logged out | Message row with user_id NULL, counted in summary | Matched expected result | PASS |
| TC-INT-03 | Frontend pages render with their forms/headings | GET /, /login, /register, /history | 200 and expected markup present | Matched expected result | PASS |
| TC-INT-03 | Frontend pages render with their forms/headings | GET /, /login, /register, /history | 200 and expected markup present | Matched expected result | PASS |
| TC-INT-03 | Frontend pages render with their forms/headings | GET /, /login, /register, /history | 200 and expected markup present | Matched expected result | PASS |
| TC-INT-03 | Frontend pages render with their forms/headings | GET /, /login, /register, /history | 200 and expected markup present | Matched expected result | PASS |
| TC-INT-04 | Frontend script targets every API endpoint the UI uses | Read static/js/script.js | References predict, history, login, register, logout, feedback, stats, train endpoints | Matched expected result | PASS |
| TC-INT-05 | History persists after the application restarts | Store a prediction, build a NEW app instance on the same database file | Record still present | records after restart: 1 | PASS |
| TC-MOD-01 | Classifier rejects empty messages | '' and '   ' | ValueError | Matched expected result | PASS |
| TC-MOD-02 | Classifier rejects non-string input | None, 42, ['a'] | ValueError | Matched expected result | PASS |
| TC-MOD-03 | Prediction result structure | 'Win a free prize now' | label in {spam,ham}, probabilities sum to 1, confidence in [0.5,1] | {'prediction': 'spam', 'is_spam': True, 'spam_probability': 0.9986037741196031, 'ham_probability': 0.0013962258803968952, 'confidence': 0.9986037741196031} | PASS |
| TC-MOD-04 | Hand-written unseen SPAM messages | 8 new spam messages | At least 7 of 8 classified as spam | 7/8 classified as spam | PASS |
| TC-MOD-05 | Hand-written unseen LEGITIMATE messages | 8 new ham messages | At least 7 of 8 classified as not spam | 8/8 classified as ham | PASS |
| TC-MOD-06 | Missing model files are reported clearly | SpamClassifier pointing at nonexistent files | is_ready() False and load() raises FileNotFoundError | Matched expected result | PASS |
| TC-MOD-07 | Metrics on the held-out 20% test split of the SMS Spam Collection | Stratified split, random_state=42 | accuracy>=0.97, precision>=0.90, recall>=0.85, F1>=0.90 | accuracy=0.9913 precision=0.9760 recall=0.9531 f1=0.9644 on 1032 messages | PASS |
| TC-MOD-08 | Dataset loader removes missing and duplicate rows | CSV with duplicate text, empty text and unknown label | Only valid unique rows remain | Matched expected result | PASS |
| TC-PRE-01 | Text preprocessing lowercases, strips punctuation and stop words | 'Hello, WORLD!! The cats are running.' | Lowercase stemmed tokens, no punctuation or stop words | Matched expected result | PASS |
| TC-PRE-02 | URLs, phone numbers and currency are normalised | 'Call 09061701461 or visit http://x.com for £100' | urltoken, longnumtoken and currencytoken present | Matched expected result | PASS |
| TC-PRE-03 | Preprocessing handles empty / non-string input safely | None, 123, '', '   ', '!!!???' | Returns an empty string without raising | Matched expected result | PASS |
| TC-PRE-03 | Preprocessing handles empty / non-string input safely | None, 123, '', '   ', '!!!???' | Returns an empty string without raising | Matched expected result | PASS |
| TC-PRE-03 | Preprocessing handles empty / non-string input safely | None, 123, '', '   ', '!!!???' | Returns an empty string without raising | Matched expected result | PASS |
| TC-PRE-03 | Preprocessing handles empty / non-string input safely | None, 123, '', '   ', '!!!???' | Returns an empty string without raising | Matched expected result | PASS |
| TC-PRE-03 | Preprocessing handles empty / non-string input safely | None, 123, '', '   ', '!!!???' | Returns an empty string without raising | Matched expected result | PASS |
| TC-SEC-08 | Control characters are stripped from input | 'free\x00 prize\x07 now' | Stored text has no control characters | Matched expected result | PASS |
| TC-SEC-09 | Users can only see and delete their own history | User A creates a record; user B reads/deletes it | B gets 404 and a different list | Matched expected result | PASS |
| TC-SEC-10 | Search term with SQL / LIKE wildcards | q="' OR 1=1 --" and q='%' | No SQL error; wildcard treated literally (0 matches) | inj total=0, '%' total=0 | PASS |
| TC-SEC-11 | Feedback on another user's message is refused | B submits feedback for A's message | 404 | Matched expected result | PASS |
| TC-SEC-12 | XSS payload is stored as text and never injected as markup | message '<script>alert(1)</script> free prize' | Pages don't contain the raw payload; API returns it as JSON data | Matched expected result | PASS |
