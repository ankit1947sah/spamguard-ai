"""Train, compare and save the spam classifiers.

Usage:
    python -m ml_model.train_model                       # uses dataset/spam.csv
    python -m ml_model.train_model --data my_data.csv    # your own CSV (label + text columns)
    python -m ml_model.train_model --log-db              # also write results to MySQL model_logs
"""
import argparse
import json
import os
import sys

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix,
                             f1_score, precision_score, recall_score)
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline

if __package__ in (None, ""):  # allow `python ml_model/train_model.py`
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml_model.preprocess import clean_text  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA = os.path.join(os.path.dirname(HERE), "dataset", "spam.csv")
MODEL_PATH = os.path.join(HERE, "spam_model.pkl")
VECTORIZER_PATH = os.path.join(HERE, "vectorizer.pkl")
METRICS_PATH = os.path.join(HERE, "metrics.json")

RANDOM_STATE = 42
TEST_SIZE = 0.2
LABEL_COLS = ("label", "v1", "category", "class", "type", "target")
TEXT_COLS = ("text", "v2", "message", "sms", "email", "body")
LABEL_MAP = {"spam": 1, "ham": 0, "legitimate": 0, "not spam": 0, "not_spam": 0, "1": 1, "0": 0}


def new_vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)


def candidate_models() -> dict:
    return {
        "Multinomial Naive Bayes": MultinomialNB(alpha=0.1),
        "Logistic Regression": LogisticRegression(max_iter=1000, C=10, class_weight="balanced"),
    }


def load_dataset(path: str = DEFAULT_DATA) -> pd.DataFrame:
    """Load a CSV/TSV of labelled messages -> DataFrame[text, label(0/1)].

    Handles the standard Kaggle `spam.csv` (v1,v2, latin-1), headed files with
    label/text style columns, and header-less two-column files.
    Missing values and duplicate messages are removed.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Dataset not found: {path}")
    sep = "\t" if path.lower().endswith((".tsv", ".txt")) else ","
    df = None
    for enc in ("utf-8", "latin-1"):
        try:
            df = pd.read_csv(path, sep=sep, encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    if df is None:
        raise ValueError("Could not decode the dataset file.")

    cols = {str(c).strip().lower(): c for c in df.columns}
    label_col = next((cols[c] for c in LABEL_COLS if c in cols), None)
    text_col = next((cols[c] for c in TEXT_COLS if c in cols), None)
    if label_col is None or text_col is None:
        # header-less file: re-read using the first two columns as label,text
        raw = pd.read_csv(path, sep=sep, encoding="latin-1", header=None)
        if raw.shape[1] < 2:
            raise ValueError("Dataset needs a label column and a text column.")
        df = raw.iloc[:, :2]
        df.columns = ["label", "text"]
    else:
        df = df[[label_col, text_col]]
        df.columns = ["label", "text"]

    df = df.dropna()
    df["label"] = df["label"].astype(str).str.strip().str.lower().map(LABEL_MAP)
    df["text"] = df["text"].astype(str).str.strip()
    df = df.dropna(subset=["label"])
    df = df[df["text"] != ""]
    df = df.drop_duplicates(subset="text").reset_index(drop=True)
    df["label"] = df["label"].astype(int)
    if df["label"].nunique() < 2 or len(df) < 50:
        raise ValueError("Dataset must contain both spam and ham rows (at least 50 messages).")
    return df


def split_dataset(df: pd.DataFrame):
    """Deterministic stratified split (reused by the tests to get genuinely held-out data)."""
    return train_test_split(df["text"], df["label"], test_size=TEST_SIZE,
                            random_state=RANDOM_STATE, stratify=df["label"])


def _metrics(y_true, y_pred) -> dict:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1_score": float(f1_score(y_true, y_pred, zero_division=0)),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist(),
        "classification_report": classification_report(
            y_true, y_pred, labels=[0, 1], target_names=["ham", "spam"], zero_division=0),
    }


def train(df: pd.DataFrame, model_path=MODEL_PATH, vectorizer_path=VECTORIZER_PATH,
          metrics_path=METRICS_PATH, verbose=True) -> dict:
    """Train both models, compare, select the best, save with joblib. Returns the metrics dict."""
    x_train, x_test, y_train, y_test = split_dataset(df)
    x_train_c = x_train.map(clean_text)
    x_test_c = x_test.map(clean_text)

    vectorizer = new_vectorizer()
    xtr = vectorizer.fit_transform(x_train_c)
    xte = vectorizer.transform(x_test_c)

    results, fitted = {}, {}
    for name, model in candidate_models().items():
        # Model selection uses 5-fold CV F1 on the TRAIN split only (no test-set peeking).
        cv_f1 = cross_val_score(make_pipeline(new_vectorizer(), model.__class__(**model.get_params())),
                                x_train_c, y_train, cv=5, scoring="f1").mean()
        model.fit(xtr, y_train)
        res = _metrics(y_test, model.predict(xte))
        res["cv_f1"] = float(cv_f1)
        results[name] = res
        fitted[name] = model
        if verbose:
            print(f"\n=== {name} ===  (5-fold CV F1 on train: {cv_f1:.4f})")
            print(f"accuracy={res['accuracy']:.4f} precision={res['precision']:.4f} "
                  f"recall={res['recall']:.4f} f1={res['f1_score']:.4f}")
            print("confusion matrix [[TN FP],[FN TP]]:", res["confusion_matrix"])
            print(res["classification_report"])

    best = max(results, key=lambda n: (results[n]["cv_f1"], results[n]["f1_score"]))
    joblib.dump(fitted[best], model_path)
    joblib.dump(vectorizer, vectorizer_path)

    summary = {
        "selected_model": best,
        "dataset_size": int(len(df)),
        "spam_count": int(df["label"].sum()),
        "ham_count": int((df["label"] == 0).sum()),
        "train_size": int(len(x_train)),
        "test_size": int(len(x_test)),
        "results": results,
    }
    with open(metrics_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    if verbose:
        print(f"\nSelected model: {best}\nSaved: {model_path}\nSaved: {vectorizer_path}")
    return summary


def log_to_database(summary: dict) -> None:
    """Write one model_logs row per trained model (requires a reachable database)."""
    from app import create_app
    from database.db import db
    from database.models import ModelLog

    app = create_app()
    with app.app_context():
        db.create_all()
        for name, res in summary["results"].items():
            db.session.add(ModelLog(model_name=name + (" (selected)" if name == summary["selected_model"] else ""),
                                    accuracy=res["accuracy"], precision=res["precision"],
                                    recall=res["recall"], f1_score=res["f1_score"]))
        db.session.commit()
    print("Model results written to model_logs.")


def main():
    parser = argparse.ArgumentParser(description="Train SpamGuard AI models")
    parser.add_argument("--data", default=DEFAULT_DATA, help="CSV/TSV dataset path")
    parser.add_argument("--log-db", action="store_true", help="store metrics in the model_logs table")
    args = parser.parse_args()

    df = load_dataset(args.data)
    print(f"Loaded {len(df)} unique messages ({df['label'].sum()} spam / {(df['label'] == 0).sum()} ham)")
    summary = train(df)
    if args.log_db:
        log_to_database(summary)


if __name__ == "__main__":
    main()
