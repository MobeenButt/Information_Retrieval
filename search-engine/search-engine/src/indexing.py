"""Inverted index for the structured-document search engine.

Handles BOTH the structured ``documents.json`` corpus (research papers with
title / abstract / methodology / results / category fields) and a folder of
flat files (.txt, .json, .csv, .xml).

The index stores a positional inverted index (term -> {doc_id -> {tf, positions}})
plus a separate per-field index (field -> term -> {doc_id -> tf}) used by the
Week 4 structured retrieval models.
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Dict, List, Optional

from text_processing import preprocess

# Week 1 - Default per-field boost applied when building the combined index.
# Title words count twice (as in the Week 1 lecture); body fields count once.
DEFAULT_FIELD_WEIGHTS: Dict[str, int] = {
    "title": 2,
    "abstract": 1,
    "methodology": 1,
    "results": 1,
    "category": 1,
    "text": 1,
}

# Files that are not treated as flat documents when indexing a whole folder
# (they are the structured corpus / judgments, not single documents).
_FOLDER_SKIP = {"documents.json", "relevance_judgments.json"}


# ─────────────────────────────────────────────
#  Flat-file readers (Week 1 - Document acquisition)
# ─────────────────────────────────────────────
def _read_txt(path: str) -> Dict[str, str]:
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.read().strip().splitlines()
    title = os.path.splitext(os.path.basename(path))[0].replace("_", " ")
    if lines and lines[0].lower().startswith("title:"):
        title = lines[0].split(":", 1)[1].strip()
        lines = lines[1:]
    return {"title": title, "text": " ".join(l.strip() for l in lines if l.strip())}


def _flatten_json(obj, parts: Optional[List[str]] = None) -> List[str]:
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


def _read_json_flat(path: str) -> Dict[str, str]:
    title = os.path.splitext(os.path.basename(path))[0].replace("_", " ")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for key in ("title", "name", "subject", "heading"):
                if key in data and isinstance(data[key], str):
                    title = data[key]
                    break
        return {"title": title, "text": " ".join(_flatten_json(data))}
    except Exception as e:  # noqa: BLE001 - surface a readable body, never crash
        return {"title": title, "text": f"[JSON read error: {e}]"}


def _read_csv(path: str) -> Dict[str, str]:
    title = os.path.splitext(os.path.basename(path))[0].replace("_", " ")
    parts: List[str] = []
    try:
        with open(path, encoding="utf-8", errors="replace", newline="") as f:
            for row in csv.reader(f):
                parts.extend(cell for cell in row if cell.strip())
        return {"title": title, "text": " ".join(parts)}
    except Exception as e:  # noqa: BLE001
        return {"title": title, "text": f"[CSV read error: {e}]"}


def _read_xml(path: str) -> Dict[str, str]:
    title = os.path.splitext(os.path.basename(path))[0].replace("_", " ")
    try:
        root = ET.parse(path).getroot()
        texts: List[str] = []
        for elem in root.iter():
            tag = re.sub(r"\{.*?\}", "", elem.tag).lower()
            if tag in ("title", "name", "heading") and elem.text and elem.text.strip():
                title = elem.text.strip()
            if elem.text and elem.text.strip():
                texts.append(elem.text.strip())
            if elem.tail and elem.tail.strip():
                texts.append(elem.tail.strip())
        return {"title": title, "text": " ".join(texts)}
    except Exception as e:  # noqa: BLE001
        return {"title": title, "text": f"[XML read error: {e}]"}


_READERS = {
    ".txt": _read_txt,
    ".json": _read_json_flat,
    ".csv": _read_csv,
    ".xml": _read_xml,
}


# ─────────────────────────────────────────────
#  Week 1/Week 3 - Inverted index
# ─────────────────────────────────────────────
class InvertedIndex:
    """Positional inverted index plus a per-field index and ranking statistics."""

    def __init__(self) -> None:
        # term -> {doc_id: {"tf": int, "positions": [int, ...]}}
        self.postings: Dict[str, Dict[int, Dict]] = {}
        # field -> term -> {doc_id: tf}
        self.field_postings: Dict[str, Dict[str, Dict[int, int]]] = {}
        self.field_doc_len: Dict[str, Dict[int, int]] = {}  # field -> doc_id -> field length
        self.doc_len: Dict[int, int] = {}      # doc_id -> length of combined stream
        self.avg_len: float = 0.0
        self.avg_field_len: Dict[str, float] = {}           # field -> mean field length
        self.vocabulary: List[str] = []       # sorted list of all terms
        self.docs: Dict[int, Dict] = {}       # doc_id -> full document dict
        self._norms: Dict[int, float] = {}     # tf-idf vector norms (cosine)

    # ── building ──────────────────────────────
    def add_document(self, doc_id: int, fields: Dict[str, str],
                     field_weights: Optional[Dict[str, int]] = None) -> None:
        """Index one document given its named text fields.

        ``fields`` maps field name -> raw text (e.g. {"title": ..., "abstract": ...}).
        ``field_weights`` multiplies a field's contribution to the combined
        positional index (title words count twice by default). The per-field
        index records the *raw* term frequency per field (no weighting) so that
        field-specific search is faithful to that field.
        """
        weights = dict(DEFAULT_FIELD_WEIGHTS)
        if field_weights:
            weights.update(field_weights)

        # store the full document
        doc = {"id": doc_id}
        doc.update(fields)
        self.docs[doc_id] = doc

        stream: List[str] = []
        for field, text in fields.items():
            tokens = preprocess(text or "")
            # per-field postings (raw tf, unweighted) and per-field length
            fpost = self.field_postings.setdefault(field, {})
            self.field_doc_len.setdefault(field, {})[doc_id] = len(tokens)
            for tok in tokens:
                fpost.setdefault(tok, {}).setdefault(doc_id, 0)
                fpost[tok][doc_id] += 1
            # combined positional stream, with the field boost applied
            w = max(1, int(weights.get(field, 1)))
            for tok in tokens:
                stream.extend([tok] * w)

        for pos, tok in enumerate(stream):
            entry = self.postings.setdefault(tok, {}).setdefault(
                doc_id, {"tf": 0, "positions": []}
            )
            entry["tf"] += 1
            entry["positions"].append(pos)

        self.doc_len[doc_id] = len(stream)

    def finalize(self) -> None:
        """Recompute collection-level statistics once all documents are added."""
        n = max(1, len(self.docs))
        self.avg_len = sum(self.doc_len.values()) / n
        self.vocabulary = sorted(self.postings.keys())
        # average length per field (only over documents that have that field)
        for field, lens in self.field_doc_len.items():
            self.avg_field_len[field] = (sum(lens.values()) / len(lens)) if lens else 0.0
        squares: Dict[int, float] = defaultdict(float)
        for term, plist in self.postings.items():
            idf = self.idf(term)
            for doc_id, entry in plist.items():
                w = (1 + math.log(entry["tf"])) * idf
                squares[doc_id] += w * w
        self._norms = {d: math.sqrt(squares[d]) or 1.0 for d in self.docs}

    # ── statistics ────────────────────────────
    @property
    def n_docs(self) -> int:
        return len(self.docs)

    def df(self, term: str) -> int:
        """Document frequency: number of documents containing ``term``."""
        return len(self.postings.get(term, {}))

    def idf(self, term: str) -> float:
        """Inverse document frequency with +1 smoothing: idf = ln(1 + N/df)."""
        df = self.df(term)
        return math.log(1 + self.n_docs / df) if df else 0.0

    def norm(self, doc_id: int) -> float:
        """Pre-computed TF-IDF vector length of a document (for cosine)."""
        return self._norms.get(doc_id, 1.0)

    def document_text(self, doc_id: int) -> str:
        """Concatenate all textual fields of a document (for snippets)."""
        doc = self.docs.get(doc_id, {})
        return " ".join(str(v) for k, v in doc.items() if k != "id" and k != "category")

    # ── formal document-term matrix view ──────
    def forward_index(self) -> Dict[int, Dict[str, float]]:
        """Return w_ij = (1 + ln tf) * idf for every (doc, term) pair.

        Week 3 - Forward (index-term) view of the collection: the formal
        document-term weight matrix used by the Vector Space Model.
        """
        fwd: Dict[int, Dict[str, float]] = {d: {} for d in self.docs}
        for term, plist in self.postings.items():
            idf = self.idf(term)
            for doc_id, entry in plist.items():
                fwd[doc_id][term] = (1 + math.log(entry["tf"])) * idf
        return fwd

    # ── persistence ──────────────────────────
    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "postings": self.postings,
                "field_postings": self.field_postings,
                "field_doc_len": self.field_doc_len,
                "doc_len": self.doc_len,
                "docs": self.docs,
            }, f)

    @classmethod
    def load(cls, path: str) -> "InvertedIndex":
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        idx = cls()
        idx.postings = {
            t: {int(d): v for d, v in p.items()}
            for t, p in raw["postings"].items()
        }
        idx.field_postings = {
            fld: {t: {int(d): v for d, v in p.items()} for t, p in terms.items()}
            for fld, terms in raw["field_postings"].items()
        }
        idx.field_doc_len = {
            fld: {int(d): v for d, v in lens.items()}
            for fld, lens in raw.get("field_doc_len", {}).items()
        }
        idx.doc_len = {int(d): v for d, v in raw["doc_len"].items()}
        idx.docs = {int(d): v for d, v in raw["docs"].items()}
        idx.finalize()
        return idx

    # ── builders ─────────────────────────────
    @classmethod
    def build_from_json(cls, json_path: str) -> "InvertedIndex":
        """Build the index from a structured documents.json array."""
        with open(json_path, encoding="utf-8") as f:
            documents = json.load(f)
        idx = cls()
        for doc in documents:
            doc_id = int(doc["id"])
            fields = {k: str(v) for k, v in doc.items() if k != "id"}
            idx.add_document(doc_id, fields)
        idx.finalize()
        return idx

    @classmethod
    def build_from_folder(cls, folder_path: str) -> "InvertedIndex":
        """Build the index from a folder of flat files (.txt/.json/.csv/.xml).

        Each file becomes one document with ``title`` and ``text`` fields.
        The structured ``documents.json`` and ``relevance_judgments.json`` are
        skipped so a folder can hold both corpora without conflict.
        """
        idx = cls()
        doc_id = 1
        for name in sorted(os.listdir(folder_path)):
            if name in _FOLDER_SKIP:
                continue
            ext = os.path.splitext(name)[1].lower()
            reader = _READERS.get(ext)
            if reader is None:
                continue
            fields = reader(os.path.join(folder_path, name))
            if not fields:
                continue
            idx.add_document(doc_id, fields)
            doc_id += 1
        idx.finalize()
        return idx

    @classmethod
    def load_or_build(cls, index_path: str, json_path: Optional[str] = None,
                      folder_path: Optional[str] = None,
                      force: bool = False) -> "InvertedIndex":
        """Reuse a saved index, or build (and save) one from json or folder."""
        if not force and os.path.exists(index_path):
            return cls.load(index_path)
        if json_path and os.path.exists(json_path):
            idx = cls.build_from_json(json_path)
        elif folder_path and os.path.isdir(folder_path):
            idx = cls.build_from_folder(folder_path)
        else:
            raise FileNotFoundError(
                "No corpus to index: provide a valid json_path or folder_path."
            )
        idx.save(index_path)
        return idx
