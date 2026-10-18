"""Probabilistic ranking models (Week 4).

Contains:
  - sigmoid                 logistic P(relevance) = 1 / (1 + e^-s)
  - rsj_weight              Robertson-Sparck Jones term weight (BIM)
  - bim_search              Binary Independence Model ranking
  - bm25_score / bm25_search  Okapi BM25 ranking
  - bm25_explain            per-term BM25 math walkthrough
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

from text_processing import preprocess


# ─────────────────────────────────────────────
#  Week 4 - Probabilistic Models
# ─────────────────────────────────────────────
def sigmoid(s: float) -> float:
    """Logistic sigmoid: P = 1 / (1 + e^-s), mapping any score to a probability."""
    if s >= 0:
        z = math.exp(-s)
        return 1.0 / (1.0 + z)
    z = math.exp(s)
    return z / (1.0 + z)


def verify_sigmoid_example() -> Dict[str, object]:
    """Verify sigmoid(3.5)=0.9707, sigmoid(2.0)=0.8808, sigmoid(4.8)=0.9918 (within 0.001)."""
    inputs = [3.5, 2.0, 4.8]
    expected = [0.9707, 0.8808, 0.9918]
    values = [sigmoid(s) for s in inputs]
    for v, e in zip(values, expected):
        assert abs(v - e) < 0.001, f"sigmoid check failed: {v} != {e}"
    return {
        "inputs": inputs,
        "sigmoid": [round(v, 4) for v in values],
        "expected": expected,
    }


def rsj_weight(r: int, R: int, n: int, N: int) -> float:
    """Robertson-Sparck Jones term weight with 0.5 smoothing.

    w(t) = ln[ (r + 0.5)(N - n + 0.5) / ((n - r + 0.5)(R - r + 0.5)) ]

    r = # relevant docs containing t ; R = # relevant docs total
    n = # docs containing t           ; N = # docs total
    With no relevance feedback (R = r = 0) the 0.5 factors cancel and the
    weight reduces to the familiar IDF-like ln[(N - n + 0.5)/(n + 0.5)].
    """
    num = (r + 0.5) * (N - n + 0.5)
    den = (n - r + 0.5) * (R - r + 0.5)
    return math.log(max(num / max(den, 1e-9), 1e-9))


def bim_search(query: str, index, relevant_ids: Optional[List[int]] = None,
               top_k: int = 10) -> List[Dict]:
    """Binary Independence Model ranking.

    Score of a document = sum of RSJ weights of the query terms it contains;
    the score is then mapped through the sigmoid to a relevance probability.
    """
    terms = preprocess(query)
    N = index.n_docs
    rel_set = set(relevant_ids) if relevant_ids else set()
    R = len(rel_set)

    term_weights: Dict[str, float] = {}
    for term in set(terms):
        plist = index.postings.get(term, {})
        n = len(plist)
        r = sum(1 for d in plist if d in rel_set)
        term_weights[term] = rsj_weight(r, R, n, N)

    scores: Dict[int, float] = {}
    for doc_id in index.docs:
        s = 0.0
        for term, w in term_weights.items():
            if doc_id in index.postings.get(term, {}):
                s += w
        if s != 0.0:
            scores[doc_id] = s

    ordered = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    hits: List[Dict] = []
    for doc_id, s in ordered[:top_k]:
        doc = index.docs.get(doc_id, {})
        hits.append({
            "id": doc_id,
            "title": doc.get("title", ""),
            "category": doc.get("category", ""),
            "score": round(s, 4),
            "probability": round(sigmoid(s), 4),
            "term_weights": {t: round(w, 4) for t, w in term_weights.items()},
            "matched": [t for t in dict.fromkeys(terms)
                        if doc_id in index.postings.get(t, {})],
        })
    return hits


# ── Okapi BM25 ────────────────────────────────
def bm25_score(query_terms: List[str], doc_id: int, index,
               k1: float = 1.5, b: float = 0.75) -> float:
    """Okapi BM25 score of a single document for the given query terms."""
    N = index.n_docs
    avgdl = index.avg_len or 1.0
    dl = index.doc_len.get(doc_id, 0)
    score = 0.0
    for term in set(query_terms):
        plist = index.postings.get(term, {})
        df = len(plist)
        if df == 0:
            continue
        entry = plist.get(doc_id)
        if not entry:
            continue
        tf = entry["tf"]
        idf = math.log(1 + (N - df + 0.5) / (df + 0.5))
        norm = k1 * (1 - b + b * dl / avgdl)
        score += idf * tf * (k1 + 1) / (tf + norm)
    return score


def bm25_explain(query_terms: List[str], doc_id: int, index,
                 k1: float = 1.5, b: float = 0.75) -> str:
    """Per-term BM25 walkthrough: tf, df, idf, doc_len, avgdl, length_norm,
    term_score, then the total score.
    """
    N = index.n_docs
    avgdl = index.avg_len or 1.0
    dl = index.doc_len.get(doc_id, 0)
    doc = index.docs.get(doc_id, {})
    lines = [
        f"BM25 explanation  -  doc {doc_id}: {doc.get('title', '')}",
        f"N = {N}   avgdl = {avgdl:.2f}   doc_len = {dl}   k1 = {k1}   b = {b}",
        f"length normalization factor = k1*(1 - b + b*|d|/avgdl)",
        "",
    ]
    total = 0.0
    for term in dict.fromkeys(query_terms):
        plist = index.postings.get(term, {})
        df = len(plist)
        if df == 0:
            lines.append(f"  term='{term}': not in collection (df = 0) -> term_score = 0.0000")
            continue
        entry = plist.get(doc_id)
        tf = entry["tf"] if entry else 0
        idf = math.log(1 + (N - df + 0.5) / (df + 0.5))
        length_norm = k1 * (1 - b + b * dl / avgdl)
        term_score = idf * tf * (k1 + 1) / (tf + length_norm) if tf > 0 else 0.0
        total += term_score
        lines.append(
            f"  term='{term}': tf={tf}  df={df}  idf={idf:.4f}  "
            f"length_norm={length_norm:.4f}  -> term_score={term_score:.4f}"
        )
    lines += ["", f"  TOTAL BM25 score = {total:.4f}"]
    return "\n".join(lines)


def bm25_search(query: str, index, k1: float = 1.5, b: float = 0.75,
                top_k: int = 10, show_math: bool = False) -> List[Dict]:
    """Rank documents with Okapi BM25. Optionally attach a per-doc math trace."""
    terms = preprocess(query)
    N = index.n_docs
    avgdl = index.avg_len or 1.0
    scores: Dict[int, float] = {}
    for term in set(terms):
        plist = index.postings.get(term, {})
        if not plist:
            continue
        df = len(plist)
        idf = math.log(1 + (N - df + 0.5) / (df + 0.5))
        for doc_id, entry in plist.items():
            tf = entry["tf"]
            norm = k1 * (1 - b + b * index.doc_len[doc_id] / avgdl)
            scores[doc_id] = scores.get(doc_id, 0.0) + idf * tf * (k1 + 1) / (tf + norm)

    ordered = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    stems = list(dict.fromkeys(terms))
    hits: List[Dict] = []
    for doc_id, s in ordered[:top_k]:
        doc = index.docs.get(doc_id, {})
        hit = {
            "id": doc_id,
            "title": doc.get("title", ""),
            "category": doc.get("category", ""),
            "score": round(s, 4),
            "matched": [t for t in stems if doc_id in index.postings.get(t, {})],
        }
        if show_math:
            hit["explanation"] = bm25_explain(terms, doc_id, index, k1, b)
        hits.append(hit)
    return hits
