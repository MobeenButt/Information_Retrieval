"""Inverted index: term -> {doc_id: term_frequency}, plus statistics for ranking.

Supported file types
--------------------
.txt   plain text (first line may be 'Title: ...')
.pdf   extracted via pdfplumber (pip install pdfplumber)
.json  flattened key/value pairs
.csv   all cell values concatenated
.xml   text content of all elements
"""
import csv
import json
import math
import os
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

from preprocess import preprocess

TITLE_BOOST = 2   # title words count twice


# ─────────────────────────────────────────────
#  Optional PDF support
# ─────────────────────────────────────────────
try:
    import pdfplumber        # pip install pdfplumber
    _PDF_OK = True
except ImportError:
    _PDF_OK = False


# ─────────────────────────────────────────────
#  Document readers per extension
# ─────────────────────────────────────────────
def _read_txt(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.read().strip().splitlines()
    title = os.path.splitext(os.path.basename(path))[0].replace("_", " ")
    if lines and lines[0].lower().startswith("title:"):
        title = lines[0].split(":", 1)[1].strip()
        lines = lines[1:]
    return title, " ".join(l.strip() for l in lines if l.strip())


def _read_pdf(path):
    title = os.path.splitext(os.path.basename(path))[0].replace("_", " ")
    if not _PDF_OK:
        return title, f"[pdfplumber not installed – cannot read {os.path.basename(path)}]"
    try:
        with pdfplumber.open(path) as pdf:
            pages = []
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    pages.append(t)
        full_text = "\n".join(pages)
        lines = full_text.strip().splitlines()
        if lines and lines[0].lower().startswith("title:"):
            title = lines[0].split(":", 1)[1].strip()
            full_text = "\n".join(lines[1:])
        return title, full_text
    except Exception as e:
        return title, f"[PDF read error: {e}]"


def _flatten_json(obj, parts=None):
    """Recursively extract all string/number values from nested JSON."""
    if parts is None:
        parts = []
    if isinstance(obj, dict):
        for v in obj.values():
            _flatten_json(v, parts)
    elif isinstance(obj, list):
        for v in obj:
            _flatten_json(v, parts)
    else:
        parts.append(str(obj))
    return parts


def _read_json(path):
    title = os.path.splitext(os.path.basename(path))[0].replace("_", " ")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            data = json.load(f)
        # try to pull a title field
        if isinstance(data, dict):
            for key in ("title", "name", "subject", "heading"):
                if key in data and isinstance(data[key], str):
                    title = data[key]
                    break
        return title, " ".join(_flatten_json(data))
    except Exception as e:
        return title, f"[JSON read error: {e}]"


def _read_csv(path):
    title = os.path.splitext(os.path.basename(path))[0].replace("_", " ")
    parts = []
    try:
        with open(path, encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.reader(f)
            headers = None
            for row_idx, row in enumerate(reader):
                if row_idx == 0:
                    headers = row
                    parts.extend(row)
                else:
                    parts.extend(row)
        return title, " ".join(p for p in parts if p.strip())
    except Exception as e:
        return title, f"[CSV read error: {e}]"


def _read_xml(path):
    title = os.path.splitext(os.path.basename(path))[0].replace("_", " ")
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        # extract all text content
        texts = []
        for elem in root.iter():
            if elem.text and elem.text.strip():
                texts.append(elem.text.strip())
            if elem.tail and elem.tail.strip():
                texts.append(elem.tail.strip())
            # check for a title-like attribute or tag
            tag = re.sub(r'\{.*?\}', '', elem.tag).lower()
            if tag in ("title", "name", "heading"):
                if elem.text and elem.text.strip():
                    title = elem.text.strip()
        return title, " ".join(texts)
    except Exception as e:
        return title, f"[XML read error: {e}]"


READERS = {
    ".txt":  _read_txt,
    ".pdf":  _read_pdf,
    ".json": _read_json,
    ".csv":  _read_csv,
    ".xml":  _read_xml,
}

SUPPORTED_EXTENSIONS = tuple(READERS.keys())


def read_file_any(path):
    """Dispatch to the correct reader based on the file extension."""
    ext = os.path.splitext(path)[1].lower()
    reader = READERS.get(ext)
    if reader is None:
        return None, None
    return reader(path)


# ─────────────────────────────────────────────
#  Inverted Index
# ─────────────────────────────────────────────
class InvertedIndex:
    def __init__(self):
        self.docs     = {}   # doc_id -> {"id", "title", "text", "source", "file_type"}
        self.postings = {}   # term   -> {doc_id: tf}
        self.doc_len  = {}   # doc_id -> number of indexed terms
        self.norms    = {}   # doc_id -> TF-IDF vector length (cosine normalisation)
        self.avg_len  = 0.0

    # ── building ──────────────────────────────
    def add_document(self, doc_id, title, text, source="", file_type="txt"):
        self.docs[doc_id] = {
            "id": doc_id, "title": title, "text": text,
            "source": source, "file_type": file_type,
        }
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

    # ── statistics ────────────────────────────
    @property
    def n_docs(self):
        return len(self.docs)

    def df(self, term):
        return len(self.postings.get(term, ()))

    def idf(self, term):
        df = self.df(term)
        return math.log(1 + self.n_docs / df) if df else 0.0

    # ── persistence ───────────────────────────
    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "docs":     self.docs,
                "postings": self.postings,
                "doc_len":  self.doc_len,
                "norms":    self.norms,
                "avg_len":  self.avg_len,
            }, f)

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        idx = cls()
        to_int = lambda d: {int(k): v for k, v in d.items()}
        idx.docs     = to_int(raw["docs"])
        idx.postings = {t: to_int(p) for t, p in raw["postings"].items()}
        idx.doc_len  = to_int(raw["doc_len"])
        idx.norms    = to_int(raw["norms"])
        idx.avg_len  = raw["avg_len"]
        return idx


# ─────────────────────────────────────────────
#  Document collection reader
# ─────────────────────────────────────────────
def read_documents(folder):
    """Scan *folder* for all supported file types and return a list of
    (doc_id, title, text, source_filename, file_type) tuples.
    """
    docs = []
    doc_id = 1
    for name in sorted(os.listdir(folder)):
        ext = os.path.splitext(name)[1].lower()
        if ext not in READERS:
            continue
        path = os.path.join(folder, name)
        title, text = read_file_any(path)
        if title is None:
            continue
        docs.append((doc_id, title, text, name, ext.lstrip(".")))
        doc_id += 1
    return docs


# ─────────────────────────────────────────────
#  Build / load helpers
# ─────────────────────────────────────────────
def build_index(folder):
    idx = InvertedIndex()
    for doc_id, title, text, source, file_type in read_documents(folder):
        idx.add_document(doc_id, title, text, source, file_type)
    idx.finalize()
    return idx


def load_or_build(data_dir, index_path, force=False):
    """Reuse the saved index unless a document changed (or force=True)."""
    files = [
        os.path.join(data_dir, f)
        for f in os.listdir(data_dir)
        if os.path.splitext(f)[1].lower() in READERS
    ]
    if not force and os.path.exists(index_path) and files:
        newest = max(os.path.getmtime(f) for f in files)
        if os.path.getmtime(index_path) >= newest:
            return InvertedIndex.load(index_path)
    idx = build_index(data_dir)
    idx.save(index_path)
    return idx
