"""Vector Space Model (Week 3).

Documents and the query are represented as term-weight vectors. We use
TF-IDF weighting (1 + ln tf) * idf and rank documents by cosine similarity
between the query vector and each document vector.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Dict, List

from text_processing import preprocess


# ─────────────────────────────────────────────
#  Week 3 - Vector Space Model
# ─────────────────────────────────────────────
def tfidf_weight(tf: float, idf: float) -> float:
    """TF-IDF weight: (1 + ln tf) * idf. Returns 0 when the term is absent."""
    if tf <= 0:
        return 0.0
    return (1 + math.log(tf)) * idf


def build_doc_vectors(index) -> Dict[int, Dict[str, float]]:
    """Return the TF-IDF vector of every document: doc_id -> {term: weight}.

    Week 3 - Document vectors (the formal term-weight representation).
    """
    vectors: Dict[int, Dict[str, float]] = {d: {} for d in index.docs}
    for term, plist in index.postings.items():
        idf = index.idf(term)
        for doc_id, entry in plist.items():
            vectors[doc_id][term] = tfidf_weight(entry["tf"], idf)
    return vectors


def query_vector(query: str, index) -> Dict[str, float]:
    """Return the TF-IDF vector of the query: term -> weight."""
    q: Dict[str, float] = {}
    for term, qtf in Counter(preprocess(query)).items():
        idf = index.idf(term)
        if idf > 0:
            q[term] = tfidf_weight(qtf, idf)
    return q


def cosine_similarity(vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
    """Cosine of the angle between two sparse term-weight vectors."""
    if not vec1 or not vec2:
        return 0.0
    small, large = (vec1, vec2) if len(vec1) <= len(vec2) else (vec2, vec1)
    dot = sum(w * large.get(t, 0.0) for t, w in small.items())
    n1 = math.sqrt(sum(w * w for w in vec1.values()))
    n2 = math.sqrt(sum(w * w for w in vec2.values()))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


def vsm_search(query: str, index, top_k: int = 10) -> List[Dict]:
    """Rank documents by cosine similarity to the query (TF-IDF weights)."""
    qv = query_vector(query, index)
    doc_vecs = build_doc_vectors(index)
    scored: List[tuple] = []
    for doc_id, dv in doc_vecs.items():
        score = cosine_similarity(qv, dv)
        if score > 0:
            scored.append((doc_id, score))
    scored.sort(key=lambda x: (-x[1], x[0]))

    stems = list(qv.keys())
    hits: List[Dict] = []
    for doc_id, score in scored[:top_k]:
        doc = index.docs.get(doc_id, {})
        hits.append({
            "id": doc_id,
            "title": doc.get("title", ""),
            "category": doc.get("category", ""),
            "score": round(score, 4),
            "matched": [s for s in stems if doc_id in index.postings.get(s, {})],
        })
    return hits


def vsm_explain(query: str, index) -> str:
    """Show the vocabulary, vectors, dot product, norms and cosine per doc."""
    qv = query_vector(query, index)
    doc_vecs = build_doc_vectors(index)
    lines: List[str] = [
        f"Vector Space Model - explanation for: '{query}'",
        f"Query terms (stems): {list(qv.keys())}",
        f"Query vector: {{ {', '.join(f'{t}:{w:.3f}' for t,w in qv.items())} }}",
        f"|q| = {math.sqrt(sum(w*w for w in qv.values())):.4f}",
        "",
    ]
    candidates = []
    for doc_id, dv in doc_vecs.items():
        score = cosine_similarity(qv, dv)
        if score > 0:
            candidates.append((doc_id, score, dv))
    candidates.sort(key=lambda x: (-x[1], x[0]))
    for doc_id, score, dv in candidates[:10]:
        shared = {t: dv.get(t, 0.0) for t in qv}
        dot = sum(qv[t] * dv.get(t, 0.0) for t in qv)
        dnorm = math.sqrt(sum(w * w for w in dv.values()))
        lines.append(f"Doc {doc_id}: {index.docs.get(doc_id, {}).get('title', '')[:40]}")
        lines.append(f"  doc vector (shared dims): {{ {', '.join(f'{t}:{w:.3f}' for t,w in shared.items())} }}")
        lines.append(f"  dot(q,d) = {dot:.4f}   |d| = {dnorm:.4f}   cosine = {score:.4f}")
    if not candidates:
        lines.append("(no document shares a term with the query)")
    return "\n".join(lines)


def verify_slide_example() -> Dict[str, object]:
    """Reproduce the lecture cosine example with BINARY term weights.

    query = 'retrieval ranking'
    D1 = 'retrieval indexing ranking'   D2 = 'ranking search engine'
    D3 = 'database normalization'
    Binary weights (1 if a term is present). Expected cosines:
        D1 ~ 0.816   D2 ~ 0.408   D3 ~ 0.000
    """
    def _binary_vec(terms):
        return {t: 1.0 for t in terms}

    q = _binary_vec(["retrieval", "ranking"])
    d1 = _binary_vec(["retrieval", "indexing", "ranking"])
    d2 = _binary_vec(["ranking", "search", "engine"])
    d3 = _binary_vec(["database", "normalization"])

    c1 = cosine_similarity(q, d1)
    c2 = cosine_similarity(q, d2)
    c3 = cosine_similarity(q, d3)

    # Week 3 - assert the slide values to within 0.01
    assert abs(c1 - 0.816) < 0.01, f"D1 cosine {c1} != 0.816"
    assert abs(c2 - 0.408) < 0.01, f"D2 cosine {c2} != 0.408"
    assert abs(c3 - 0.000) < 0.01, f"D3 cosine {c3} != 0.000"

    return {
        "query": "retrieval ranking",
        "D1": "retrieval indexing ranking",
        "D2": "ranking search engine",
        "D3": "database normalization",
        "weighting": "binary",
        "cosine_D1": round(c1, 4),
        "cosine_D2": round(c2, 4),
        "cosine_D3": round(c3, 4),
    }
