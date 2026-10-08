"""Text processing shared by documents and queries.

Pipeline (Week 1, "Text Processing"): tokenization -> stop-word removal -> stemming.
The SAME function must be applied to documents (at index time) and queries
(at search time), otherwise terms will not match.
"""
import re

STOPWORDS = frozenset("""a about above after again all also am an and any are as at be because been
before being below between both but by can could did do does doing down during each few for from
further had has have having he her here hers him his how i if in into is it its itself just me more
most my no nor not now of off on once only or other our out over own same she should so some such
than that the their them then there these they this those through to too under until up very was we
were what when where which while who whom why will with would you your""".split())

_TOKEN = re.compile(r"[a-z0-9]+")
_VOWELS = set("aeiou")


def tokenize(text):
    """Lowercase the text and split it into alphanumeric tokens."""
    return _TOKEN.findall(text.lower())


def remove_stopwords(tokens):
    """Drop very common words ("the", "is", "of") that carry little meaning."""
    return [t for t in tokens if t not in STOPWORDS]


def _has_vowel(s):
    return any(c in _VOWELS for c in s)


def stem(word):
    """A small suffix-stripping stemmer (running -> run, indexes -> index).

    It is intentionally simple and readable (known limitation: compute vs computing
    stay different); real systems use Porter/Snowball.
    """
    w = word
    if len(w) <= 3:
        return w
    # plurals
    if w.endswith("sses"):
        w = w[:-2]
    elif w.endswith("ies") and len(w) > 4:
        w = w[:-3] + "y"
    elif w.endswith(("xes", "ches", "shes", "zes")):
        w = w[:-2]
    elif w.endswith("s") and not w.endswith(("ss", "us", "is")):
        w = w[:-1]
    # -ing / -ed
    for suf in ("ing", "ed"):
        base = w[: -len(suf)]
        if w.endswith(suf) and len(base) >= 3 and _has_vowel(base):
            w = base
            if w[-1] == w[-2] and w[-1] not in _VOWELS and w[-1] not in "lsz":
                w = w[:-1]  # running -> runn -> run
            break
    return w


def stem_all(tokens):
    return [stem(t) for t in tokens]


def preprocess(text):
    """Full pipeline: text -> list of index terms."""
    return stem_all(remove_stopwords(tokenize(text)))


def analyze(text):
    """Return every stage of the pipeline (used by the UI to show the process)."""
    tokens = tokenize(text)
    no_stop = remove_stopwords(tokens)
    return {"tokens": tokens, "no_stop": no_stop, "stems": stem_all(no_stop)}
