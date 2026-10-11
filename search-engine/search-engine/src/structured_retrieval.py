"""Structured Text Retrieval (Week 4).

Three region/field-aware retrieval strategies plus field-weighted BM25:

  - parse_field_query     split "title:x abstract:y free text" into field terms
  - field_bm25_search     BM25 with per-field weights (title=3, abstract=2, ...)
  - overlapped_lists      ALL terms must appear in the SAME region (precision)
  - non_overlapped_lists  terms may appear in SEPARATE regions (recall)
  - proximal_nodes        content match + structural closeness + relationship

The three list strategies implement the overlap / non-overlap / proximal-node
logic described in the Week 4 lecture on structured text retrieval.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple, Union

from text_processing import preprocess


# ─────────────────────────────────────────────
#  Week 4 - Structured Text Retrieval
# ─────────────────────────────────────────────
# Default per-field weights for field-weighted BM25 (title is most important).
DEFAULT_FIELD_WEIGHTS: Dict[str, float] = {
    "title": 3.0,
    "abstract": 2.0,
    "methodology": 1.0,
    "results": 1.0,
}

# Structural order of fields (used by the proximal nodes model to measure
# how close together two fields sit in a document).
FIELD_ORDER: Dict[str, int] = {
    "title": 0, "abstract": 1, "methodology": 2, "results": 3, "category": 4,
}


def _normalize_terms(query_terms: Union[str, List[str]]) -> List[str]:
    """Accept a raw query string or a list of stems; return unique stems in order."""
    if isinstance(query_terms, str):
        terms = preprocess(query_terms)
    else:
        terms = [t for t in query_terms]
    return list(dict.fromkeys(terms))


def parse_field_query(query_string: str) -> Tuple[Dict[str, str], str]:
    """Split a structured query into field-restricted terms and free text.

    "title:diabetes abstract:treatment glucose" ->
        ({"title": "diabetes", "abstract": "treatment"}, "glucose")
    """
    field_terms: Dict[str, List[str]] = {}
    free_parts: List[str] = []
    for tok in query_string.split():
        if ":" in tok:
            fld, _, word = tok.partition(":")
            if fld and word:
                field_terms.setdefault(fld.lower(), []).append(word)
                continue
        free_parts.append(tok)
    return {f: " ".join(ws) for f, ws in field_terms.items()}, " ".join(free_parts)


def field_bm25_search(query: str, index, field_weights: Optional[Dict[str, float]] = None,
                      top_k: int = 10, k1: float = 1.5, b: float = 0.75) -> List[Dict]:
    """Field-weighted BM25: weighted sum of per-field BM25 scores.

    Each field contributes its own BM25 score (using that field's postings,
    document frequency and field length), multiplied by the field weight.
    Hits carry ``field_scores`` and ``matched_fields``.
    """
    weights = dict(DEFAULT_FIELD_WEIGHTS)
    if field_weights:
        weights.update(field_weights)
    # strip field: prefixes so restricted words still contribute as query terms
    cleaned = " ".join(tok.partition(":")[2] if ":" in tok else tok for tok in query.split())
    terms = preprocess(cleaned)
    N = index.n_docs

    scores: Dict[int, float] = {}
    field_scores: Dict[int, Dict[str, float]] = {}
    matched_fields: Dict[int, set] = {}

    for field, fw in weights.items():
        fpost = index.field_postings.get(field)
        if not fpost:
            continue
        avgfl = index.avg_field_len.get(field) or 1.0
        flens = index.field_doc_len.get(field, {})
        for term in set(terms):
            plist = fpost.get(term)
            if not plist:
                continue
            df = len(plist)
            idf = math.log(1 + (N - df + 0.5) / (df + 0.5))
            for doc_id, tf in plist.items():
                dl = flens.get(doc_id, 0)
                norm = k1 * (1 - b + b * dl / avgfl)
                ts = idf * tf * (k1 + 1) / (tf + norm)
                scores[doc_id] = scores.get(doc_id, 0.0) + fw * ts
                field_scores.setdefault(doc_id, {}).setdefault(field, 0.0)
                field_scores[doc_id][field] += ts
                matched_fields.setdefault(doc_id, set()).add(field)

    ordered = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    stems = list(dict.fromkeys(terms))
    hits: List[Dict] = []
    for doc_id, s in ordered[:top_k]:
        doc = index.docs.get(doc_id, {})
        hits.append({
            "id": doc_id,
            "title": doc.get("title", ""),
            "category": doc.get("category", ""),
            "score": round(s, 4),
            "field_scores": {f: round(v, 4) for f, v in field_scores.get(doc_id, {}).items()},
            "matched_fields": sorted(matched_fields.get(doc_id, set())),
            "matched": [t for t in stems if any(
                doc_id in index.field_postings.get(f, {}).get(t, {}) for f in weights)],
        })
    return hits


def overlapped_lists(query_terms: Union[str, List[str]], index,
                     field: Optional[str] = None) -> List[Dict]:
    """Overlapped lists: ALL query terms must appear in the SAME region (field).

    Maximises precision - a document only matches if one field contains every
    query term. Score = number of query terms (all of them).
    """
    terms = _normalize_terms(query_terms)
    if not terms:
        return []
    fields = [field] if field else list(index.field_postings.keys())
    hits: List[Dict] = []
    for doc_id in index.docs:
        matched_field = None
        for f in fields:
            fpost = index.field_postings.get(f, {})
            if all(doc_id in fpost.get(t, {}) for t in terms):
                matched_field = f
                break
        if matched_field:
            doc = index.docs.get(doc_id, {})
            hits.append({
                "id": doc_id,
                "title": doc.get("title", ""),
                "category": doc.get("category", ""),
                "score": float(len(terms)),
                "matched_field": matched_field,
                "matched_terms": terms,
                "model": "overlapped_lists",
                "explanation": f"All terms {terms} co-occur in field '{matched_field}'.",
            })
    hits.sort(key=lambda h: (-h["score"], h["id"]))
    return hits


def non_overlapped_lists(query_terms: Union[str, List[str]], index,
                         field: Optional[str] = None) -> List[Dict]:
    """Non-overlapped lists: query terms may appear in SEPARATE regions.

    Maximises recall/coverage - a document matches if any term appears in any
    field. Each hit explains which term matched which region.
    """
    terms = _normalize_terms(query_terms)
    if not terms:
        return []
    fields = [field] if field else list(index.field_postings.keys())
    hits: List[Dict] = []
    for doc_id in index.docs:
        term_fields: Dict[str, str] = {}
        for t in terms:
            for f in fields:
                if doc_id in index.field_postings.get(f, {}).get(t, {}):
                    term_fields[t] = f
                    break
        if term_fields:
            doc = index.docs.get(doc_id, {})
            explanation = "; ".join(f"'{t}' matched in field '{f}'"
                                    for t, f in term_fields.items())
            hits.append({
                "id": doc_id,
                "title": doc.get("title", ""),
                "category": doc.get("category", ""),
                "score": float(len(term_fields)),
                "term_fields": term_fields,
                "matched_fields": sorted(set(term_fields.values())),
                "matched_terms": list(term_fields.keys()),
                "model": "non_overlapped_lists",
                "explanation": explanation,
            })
    hits.sort(key=lambda h: (-h["score"], h["id"]))
    return hits


def proximal_nodes(query_terms: Union[str, List[str]], index,
                   top_k: int = 10) -> List[Dict]:
    """Proximal nodes model: rank by structural closeness across nearby fields.

    score = content_match + structural_closeness + relationship_strength
    where content_match sums IDF of matched terms, structural_closeness rewards
    terms sitting in adjacent fields, and relationship_strength grows with the
    number of fields linked. ``node_connections`` records the field->terms graph.
    """
    terms = _normalize_terms(query_terms)
    if not terms:
        return []
    N = index.n_docs
    idf = {
        t: (math.log(1 + (N - index.df(t) + 0.5) / (index.df(t) + 0.5))
            if index.df(t) else 0.0)
        for t in terms
    }
    hits: List[Dict] = []
    for doc_id in index.docs:
        nodes: Dict[str, set] = {}
        for t in terms:
            for f in index.field_postings:
                if doc_id in index.field_postings.get(f, {}).get(t, {}):
                    nodes.setdefault(f, set()).add(t)
        if not nodes:
            continue
        matched_terms = set().union(*nodes.values())
        content_match = sum(idf.get(t, 0.0) for t in matched_terms)

        field_indices = sorted(FIELD_ORDER.get(f, 99) for f in nodes)
        span = field_indices[-1] - field_indices[0]
        structural_closeness = 1.0 / (1.0 + span)

        coverage = len(matched_terms) / len(terms)
        relationship_strength = coverage * (1 + 0.1 * (len(nodes) - 1))

        score = content_match + structural_closeness + relationship_strength
        node_connections = [{"field": f, "terms": sorted(ts)} for f, ts in nodes.items()]
        doc = index.docs.get(doc_id, {})
        hits.append({
            "id": doc_id,
            "title": doc.get("title", ""),
            "category": doc.get("category", ""),
            "score": round(score, 4),
            "content_match": round(content_match, 4),
            "structural_closeness": round(structural_closeness, 4),
            "relationship_strength": round(relationship_strength, 4),
            "node_connections": node_connections,
            "matched": sorted(matched_terms),
            "model": "proximal_nodes",
        })
    hits.sort(key=lambda h: (-h["score"], h["id"]))
    return hits[:top_k]
