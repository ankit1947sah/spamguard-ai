"""Inference wrapper around the saved model + vectorizer. All predictions come from the trained model."""
import os
import threading

import joblib

from ml_model.preprocess import clean_text

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(HERE, "spam_model.pkl")
VECTORIZER_PATH = os.path.join(HERE, "vectorizer.pkl")


class SpamClassifier:
    def __init__(self, model_path: str = MODEL_PATH, vectorizer_path: str = VECTORIZER_PATH):
        self.model_path = model_path
        self.vectorizer_path = vectorizer_path
        self._model = None
        self._vectorizer = None
        self._lock = threading.Lock()

    def is_ready(self) -> bool:
        return os.path.exists(self.model_path) and os.path.exists(self.vectorizer_path)

    def load(self) -> None:
        with self._lock:
            if not self.is_ready():
                raise FileNotFoundError(
                    "Model files not found. Run `python -m ml_model.train_model` first.")
            self._model = joblib.load(self.model_path)
            self._vectorizer = joblib.load(self.vectorizer_path)

    def reload(self) -> None:
        self._model = None
        self._vectorizer = None
        self.load()

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def predict(self, text: str) -> dict:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Message must be a non-empty string.")
        if not self.loaded:
            self.load()
        features = self._vectorizer.transform([clean_text(text)])
        proba = self._model.predict_proba(features)[0]
        spam_p = float(proba[list(self._model.classes_).index(1)])
        is_spam = spam_p >= 0.5
        return {
            "prediction": "spam" if is_spam else "ham",
            "is_spam": is_spam,
            "spam_probability": spam_p,
            "ham_probability": 1.0 - spam_p,
            "confidence": spam_p if is_spam else 1.0 - spam_p,
        }


classifier = SpamClassifier()


def predict_message(text: str) -> dict:
    return classifier.predict(text)
