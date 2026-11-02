"""Unit + model-performance tests for preprocessing and the trained classifier."""
import os

import pytest

from ml_model import train_model
from ml_model.predict import SpamClassifier, classifier
from ml_model.preprocess import clean_text

pytestmark = pytest.mark.skipif(not classifier.is_ready(),
                                reason="trained model not found - run python -m ml_model.train_model")

UNSEEN_SPAM = [
    "CONGRATULATIONS! You have won a free holiday voucher. Call 08712345678 now to claim your prize!",
    "URGENT: your bank account is locked. Verify now at http://bank-secure-login.example to avoid closure.",
    "Free entry to win a brand new iPhone! Text WIN to 80085 now. T&Cs apply, 18+ only.",
    "You have been selected for a cash reward of 1000 pounds. Reply YES to claim, offer ends today!",
    "Hot singles in your area want to chat. Txt CHAT to 86688 now, 150p per msg.",
    "Your mobile number has won 2 million dollars in our lucky draw, call 09050001295 to collect.",
    "Final notice: claim your free ringtone today. Text TONE to 80062 to download now.",
    "Get a loan approved in minutes with no credit check. Call now, limited time offer!",
]
UNSEEN_HAM = [
    "Hey, are we still on for dinner tonight? I can pick you up around seven.",
    "Can you send me the notes from yesterday's lecture? I missed the last part.",
    "I'll be a bit late, the bus is stuck in traffic. Start without me.",
    "Happy birthday! Hope you have a wonderful day, let's celebrate this weekend.",
    "Mom says dinner is ready, come home when you finish your practice.",
    "Don't forget to bring the project files to the meeting tomorrow morning.",
    "Thanks for helping me move yesterday, I owe you a coffee next time.",
    "The assignment deadline was moved to Friday, so we have a little more time.",
]


def test_preprocess_basic():
    """TC-PRE-01 | Text preprocessing lowercases, strips punctuation and stop words | 'Hello, WORLD!! The cats are running.' | Lowercase stemmed tokens, no punctuation or stop words"""
    out = clean_text("Hello, WORLD!! The cats are running.")
    assert out == out.lower()
    assert "," not in out and "!" not in out
    assert "the" not in out.split() and "are" not in out.split()
    assert "cat" in out.split() and "run" in out.split()


def test_preprocess_tokens():
    """TC-PRE-02 | URLs, phone numbers and currency are normalised | 'Call 09061701461 or visit http://x.com for £100' | urltoken, longnumtoken and currencytoken present"""
    out = clean_text("Call 09061701461 or visit http://x.com for £100").split()
    assert "urltoken" in out and "longnumtoken" in out and "currencytoken" in out


@pytest.mark.parametrize("value", [None, 123, "", "   ", "!!!???"])
def test_preprocess_invalid(value):
    """TC-PRE-03 | Preprocessing handles empty / non-string input safely | None, 123, '', '   ', '!!!???' | Returns an empty string without raising"""
    assert clean_text(value) == ""


def test_predict_rejects_empty():
    """TC-MOD-01 | Classifier rejects empty messages | '' and '   ' | ValueError"""
    with pytest.raises(ValueError):
        classifier.predict("")
    with pytest.raises(ValueError):
        classifier.predict("   ")


def test_predict_rejects_non_string():
    """TC-MOD-02 | Classifier rejects non-string input | None, 42, ['a'] | ValueError"""
    for bad in (None, 42, ["a"]):
        with pytest.raises(ValueError):
            classifier.predict(bad)


def test_predict_output_shape(actual):
    """TC-MOD-03 | Prediction result structure | 'Win a free prize now' | label in {spam,ham}, probabilities sum to 1, confidence in [0.5,1]"""
    r = classifier.predict("Win a free prize now, call 09061701461")
    actual(r)
    assert r["prediction"] in ("spam", "ham")
    assert abs(r["spam_probability"] + r["ham_probability"] - 1) < 1e-9
    assert 0.5 <= r["confidence"] <= 1.0


def test_unseen_spam(actual):
    """TC-MOD-04 | Hand-written unseen SPAM messages | 8 new spam messages | At least 7 of 8 classified as spam"""
    hits = [classifier.predict(m)["prediction"] == "spam" for m in UNSEEN_SPAM]
    actual(f"{sum(hits)}/8 classified as spam")
    assert sum(hits) >= 7


def test_unseen_ham(actual):
    """TC-MOD-05 | Hand-written unseen LEGITIMATE messages | 8 new ham messages | At least 7 of 8 classified as not spam"""
    hits = [classifier.predict(m)["prediction"] == "ham" for m in UNSEEN_HAM]
    actual(f"{sum(hits)}/8 classified as ham")
    assert sum(hits) >= 7


def test_missing_model_files(tmp_path):
    """TC-MOD-06 | Missing model files are reported clearly | SpamClassifier pointing at nonexistent files | is_ready() False and load() raises FileNotFoundError"""
    clf = SpamClassifier(str(tmp_path / "nope.pkl"), str(tmp_path / "nope2.pkl"))
    assert clf.is_ready() is False
    with pytest.raises(FileNotFoundError):
        clf.load()


@pytest.mark.skipif(not os.path.exists(train_model.DEFAULT_DATA), reason="dataset/spam.csv missing")
def test_heldout_metrics(actual):
    """TC-MOD-07 | Metrics on the held-out 20% test split of the SMS Spam Collection | Stratified split, random_state=42 | accuracy>=0.97, precision>=0.90, recall>=0.85, F1>=0.90"""
    from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

    df = train_model.load_dataset()
    _, x_test, _, y_test = train_model.split_dataset(df)
    preds = [classifier.predict(t)["is_spam"] for t in x_test]
    acc, p = accuracy_score(y_test, preds), precision_score(y_test, preds)
    r, f = recall_score(y_test, preds), f1_score(y_test, preds)
    actual(f"accuracy={acc:.4f} precision={p:.4f} recall={r:.4f} f1={f:.4f} on {len(y_test)} messages")
    assert acc >= 0.97 and p >= 0.90 and r >= 0.85 and f >= 0.90


def test_dataset_loader_cleaning(tmp_path):
    """TC-MOD-08 | Dataset loader removes missing and duplicate rows | CSV with duplicate text, empty text and unknown label | Only valid unique rows remain"""
    rows = ["label,text"] + [f"ham,message number {i} hello there" for i in range(30)]
    rows += [f"spam,win free prize number {i} now" for i in range(30)]
    rows += ["ham,message number 1 hello there", "spam,", "weird,something"]
    p = tmp_path / "d.csv"
    p.write_text("\n".join(rows), encoding="utf-8")
    df = train_model.load_dataset(str(p))
    assert len(df) == 60 and set(df["label"]) == {0, 1}
