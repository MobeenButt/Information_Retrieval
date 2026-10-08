"""Inverted index: term -> {doc_id: term_frequency}, plus statistics for ranking."""
import json
import math
import os
from collections import Counter, defaultdict

from preprocess import preprocess

TITLE_BOOST = 2  # title words count twice: a word in the title says more about the topic


class InvertedIndex:
    def __init__(self):
        self.docs = {}       # doc_id -> {"id", "title", "text"}
        self.postings = {}   # term -> {doc_id: tf}
        self.doc_len = {}    # doc_id -> number of indexed terms
        self.norms = {}      # doc_id -> length of TF-IDF vector (for cosine normalisation)
        self.avg_len = 0.0

    # ---- building -------------------------------------------------------
    def add_document(self, doc_id, title, text):
        self.docs[doc_id] = {"id": doc_id, "title": title, "text": text}
        terms = preprocess(title) * TITLE_BOOST + preprocess(text)
        for term, tf in Counter(terms).items():
            self.postings.setdefault(term, {})[doc_id] = tf
        self.doc_len[doc_id] = len(terms)

    def finalize(self):
        """Compute collection statistics once all documents are added."""
        n = max(1, len(self.docs))
        self.avg_len = sum(self.doc_len.values()) / n
        squares = defaultdict(float)
        for term, plist in self.postings.items():
            idf = self.idf(term)
            for doc_id, tf in plist.items():
                w = (1 + math.log(tf)) * idf
                squares[doc_id] += w * w
        self.norms = {d: math.sqrt(squares[d]) or 1.0 for d in self.docs}

    # ---- statistics -----------------------------------------------------
    @property
    def n_docs(self):
        return len(self.docs)

    def df(self, term):
        """Document frequency: in how many documents does the term appear?"""
        return len(self.postings.get(term, ()))

    def idf(self, term):
        """Inverse document frequency: rare terms get a higher weight."""
        df = self.df(term)
        return math.log(1 + self.n_docs / df) if df else 0.0

    # ---- persistence ----------------------------------------------------
    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"docs": self.docs, "postings": self.postings,
                       "doc_len": self.doc_len, "norms": self.norms,
                       "avg_len": self.avg_len}, f)

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        idx = cls()
        to_int = lambda d: {int(k): v for k, v in d.items()}
        idx.docs = to_int(raw["docs"])
        idx.postings = {t: to_int(p) for t, p in raw["postings"].items()}
        idx.doc_len = to_int(raw["doc_len"])
        idx.norms = to_int(raw["norms"])
        idx.avg_len = raw["avg_len"]
        return idx


def read_documents(folder):
    """Read *.txt files. First line: 'Title: ...'; the rest is the body."""
    docs = []
    for i, name in enumerate(sorted(f for f in os.listdir(folder) if f.endswith(".txt")), 1):
        with open(os.path.join(folder, name), encoding="utf-8") as f:
            lines = f.read().strip().splitlines()
        title = os.path.splitext(name)[0].replace("_", " ")
        if lines and lines[0].lower().startswith("title:"):
            title = lines[0].split(":", 1)[1].strip()
            lines = lines[1:]
        docs.append((i, title, " ".join(l.strip() for l in lines if l.strip())))
    return docs


def build_index(folder):
    idx = InvertedIndex()
    for doc_id, title, text in read_documents(folder):
        idx.add_document(doc_id, title, text)
    idx.finalize()
    return idx


def load_or_build(data_dir, index_path, force=False):
    """Reuse the saved index unless a document changed (or force=True)."""
    files = [os.path.join(data_dir, f) for f in os.listdir(data_dir) if f.endswith(".txt")]
    if not force and os.path.exists(index_path):
        newest = max((os.path.getmtime(f) for f in files), default=0)
        if os.path.getmtime(index_path) >= newest:
            return InvertedIndex.load(index_path)
    idx = build_index(data_dir)
    idx.save(index_path)
    return idx
