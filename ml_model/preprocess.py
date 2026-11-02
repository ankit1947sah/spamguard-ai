"""Text preprocessing shared by training and prediction (must stay identical in both)."""
import re
from functools import lru_cache

from nltk.stem import PorterStemmer

_stemmer = PorterStemmer()

URL_RE = re.compile(r"(https?://\S+|www\.\S+)")
EMAIL_RE = re.compile(r"\S+@\S+\.\S+")
LONG_NUMBER_RE = re.compile(r"\d{5,}")  # phone numbers, short codes
CURRENCY_RE = re.compile(r"[£$€]")
NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]")


# A fixed, bundled stop-word list keeps training and prediction identical on every machine
# (no NLTK corpus download needed). NLTK's PorterStemmer is still used for stemming.
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS  # noqa: E402

STOPWORDS = frozenset(ENGLISH_STOP_WORDS)


@lru_cache(maxsize=50000)
def _stem(word: str) -> str:
    return _stemmer.stem(word)


def clean_text(text) -> str:
    """Lowercase, normalise URLs/numbers/currency, strip punctuation, drop stop words, stem."""
    if not isinstance(text, str):
        return ""
    t = text.lower()
    t = URL_RE.sub(" urltoken ", t)
    t = EMAIL_RE.sub(" emailtoken ", t)
    t = LONG_NUMBER_RE.sub(" longnumtoken ", t)
    t = CURRENCY_RE.sub(" currencytoken ", t)
    t = NON_ALNUM_RE.sub(" ", t)
    tokens = [w for w in t.split() if w not in STOPWORDS and len(w) > 1]
    return " ".join(_stem(w) for w in tokens)
