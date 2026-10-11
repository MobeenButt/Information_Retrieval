"""Ranking models.

Models implemented
------------------
tfidf       TF-IDF cosine similarity          (Vector Space Model)
bm25        Okapi BM25                         (probabilistic)
boolean     AND / OR / NOT exact matching      (set-based, unranked)
overlap     |Q ∩ D|  keyword overlap           (set-based, ranked)
nonoverlap  Q \\ D   missing terms             (set-based, ranked by overlap)
bim         Binary Independence Model          (probabilistic, Robertson-Sparck Jones)
proximal    Proximal Nodes Model               (positional / proximity-based ranking)

Each ranked model returns {doc_id: float_score}.
boolean_search returns a set of matching doc_ids.
"""
import math
from collections import Counter, defaultdict


# ─────────────────────────────────────────────
#  1. TF-IDF  (Vector Space Model)
# ─────────────────────────────────────────────
def tfidf_scores(index, terms):
    """TF-IDF with cosine-style length normalisation.

    weight(term, doc) = (1 + log tf) * idf
    score = Σ(query_w * doc_w) / |doc vector|
    """
    scores = defaultdict(float)
    for term, qtf in Counter(terms).items():
        plist = index.postings.get(term)
        if not plist:
            continue
        idf = index.idf(term)
        q_weight = (1 + math.log(qtf)) * idf
        for doc_id, tf in plist.items():
            scores[doc_id] += q_weight * (1 + math.log(tf)) * idf
    return {d: s / index.norms[d] for d, s in scores.items()}


# ─────────────────────────────────────────────
#  2. BM25
# ─────────────────────────────────────────────
def bm25_scores(index, terms, k1=1.5, b=0.75):
    """Okapi BM25: saturating term frequency + document-length normalisation."""
    scores = defaultdict(float)
    n = index.n_docs
    for term in set(terms):
        plist = index.postings.get(term)
        if not plist:
            continue
        df = len(plist)
        idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
        for doc_id, tf in plist.items():
            norm = k1 * (1 - b + b * index.doc_len[doc_id] / index.avg_len)
            scores[doc_id] += idf * tf * (k1 + 1) / (tf + norm)
    return dict(scores)


# ─────────────────────────────────────────────
#  3. Boolean retrieval
# ─────────────────────────────────────────────
def boolean_search(index, terms, mode="and"):
    """Return a *set* of doc_ids that satisfy the Boolean expression.

    mode='and'  → every query term must be present  (AND)
    mode='or'   → at least one query term present   (OR)
    mode='not'  → docs that contain NO query term   (NOT / complement)
    """
    if not terms:
        return set()
    posting_sets = [set(index.postings.get(t, {}).keys()) for t in set(terms)]
    if mode == "and":
        result = posting_sets[0]
        for s in posting_sets[1:]:
            result = result & s
    elif mode == "or":
        result = set()
        for s in posting_sets:
            result = result | s
    elif mode == "not":
        all_docs = set(index.docs.keys())
        matched = set()
        for s in posting_sets:
            matched = matched | s
        result = all_docs - matched
    else:
        result = set()
    return result


def boolean_scores(index, terms, mode="or"):
    """Wrap boolean_search as a scored dict (score=1 for matches, 0 for others).
    Used so the engine can treat Boolean like the other models uniformly.
    """
    matched = boolean_search(index, terms, mode)
    return {doc_id: 1.0 for doc_id in matched}


# ─────────────────────────────────────────────
#  4. Overlap model
# ─────────────────────────────────────────────
def overlap_scores(index, terms):
    """Score = |Q ∩ D|: number of unique query terms that appear in the document.

    Every term has equal weight; term frequency and document length are ignored.
    This is the simplest keyword-overlap baseline.
    """
    query_terms = set(terms)
    scores = defaultdict(float)
    for term in query_terms:
        for doc_id in index.postings.get(term, {}):
            scores[doc_id] += 1.0
    return dict(scores)


# ─────────────────────────────────────────────
#  5. Non-overlap model
# ─────────────────────────────────────────────
def nonoverlap_scores(index, terms):
    """Score = |Q ∩ D| (same as overlap), but the result object also carries
    the set of *missing* query terms for each document (Q \\ D).

    Returns {doc_id: {"score": float, "missing": [term, ...]}}
    The caller (engine.py) uses the 'score' key for ranking and 'missing'
    for the explanation shown to the user.
    """
    query_terms = set(terms)
    overlap = defaultdict(set)
    for term in query_terms:
        for doc_id in index.postings.get(term, {}):
            overlap[doc_id].add(term)

    result = {}
    all_docs = set(index.docs.keys())
    for doc_id in all_docs:
        matched = overlap.get(doc_id, set())
        missing = sorted(query_terms - matched)
        score = float(len(matched))
        result[doc_id] = {"score": score, "missing": missing}
    return result


# ─────────────────────────────────────────────
#  6. BIM  (Binary Independence Model)
# ─────────────────────────────────────────────
def bim_scores(index, terms, relevant_ids=None):
    """Robertson-Sparck Jones weight for each query term.

    w(t) = ln [ (r + 0.5)(N - n + 0.5) / ((n - r + 0.5)(R - r + 0.5)) ]

    N   = total documents in collection
    n   = documents containing term t
    R   = number of known-relevant documents (0 if no feedback)
    r   = known-relevant documents containing t (0 if no feedback)

    With R = r = 0 the formula reduces to an IDF-like weight:
        w(t) ≈ ln((N - n + 0.5) / (n + 0.5))

    relevant_ids: optional list/set of doc_ids judged relevant (relevance feedback).
    """
    N = max(1, index.n_docs)
    R = len(relevant_ids) if relevant_ids else 0
    rel_set = set(relevant_ids) if relevant_ids else set()

    query_terms = set(terms)
    scores = defaultdict(float)

    for term in query_terms:
        plist = index.postings.get(term, {})
        n = len(plist)           # document frequency
        r = len([d for d in plist if d in rel_set])  # relevant docs with this term

        # Robertson-Sparck Jones weight (with 0.5 smoothing)
        numerator   = (r + 0.5) * (N - n + 0.5)
        denominator = (n - r + 0.5) * (R - r + 0.5) if R > 0 else (n + 0.5)
        # guard against log(<=0)
        ratio = numerator / max(denominator, 1e-9)
        w = math.log(max(ratio, 1e-9))

        for doc_id in plist:
            scores[doc_id] += w

    return dict(scores)


# ─────────────────────────────────────────────
#  7. Proximal Nodes Model
# ─────────────────────────────────────────────
def proximal_scores(index, terms, window=10, alpha=0.5):
    """Proximal Nodes Model – rewards documents where query terms appear
    close together in the text, not merely in the same document.

    Algorithm
    ---------
    For every document that contains at least one query term:
      1. Rebuild the token stream from the stored postings positions.
         Since our basic index stores only TF (not positions), we approximate
         positions by treating each document's text as a flat token list and
         looking up term offsets directly.
      2. Collect all positions of every query term in the document.
      3. Slide a window of size `window` tokens across the document.
         Each window scores +1 for every *distinct* query term it contains.
         The window score is (distinct_terms_in_window / |Q|)^2  so windows
         that contain many query terms score disproportionately higher.
      4. The document score is the sum of all window scores, scaled by the
         BM25 IDF of each term found in the best window (so rare terms still
         matter more than common ones).
      5. A proximity bonus `alpha` controls how much the positional component
         contributes relative to a baseline overlap score.

    Parameters
    ----------
    index   : InvertedIndex
    terms   : list of preprocessed query stems
    window  : sliding window size in tokens (default 10)
    alpha   : weight of proximity bonus vs. plain overlap (0 = overlap only,
              1 = proximity only).  Default 0.5 balances both.

    Returns
    -------
    {doc_id: float}
    """
    from preprocess import preprocess as _preprocess

    query_terms = list(dict.fromkeys(terms))   # unique, preserve order
    if not query_terms:
        return {}

    N = max(1, index.n_docs)
    qt_set = set(query_terms)

    # IDF weights for the rare-term bonus
    idf = {}
    for t in query_terms:
        df = len(index.postings.get(t, {}))
        idf[t] = math.log(1 + (N - df + 0.5) / (df + 0.5)) if df else 0.0

    # candidate docs: must contain at least one query term
    candidate_docs = set()
    for t in query_terms:
        candidate_docs.update(index.postings.get(t, {}).keys())

    scores = {}
    for doc_id in candidate_docs:
        doc = index.docs.get(doc_id)
        if doc is None:
            continue

        # tokenise the stored document text to get a positional sequence
        tokens = _preprocess(doc["title"] + " " + doc["text"])

        # build position lists for each query term
        positions = defaultdict(list)   # term -> [pos, pos, ...]
        for pos, tok in enumerate(tokens):
            if tok in qt_set:
                positions[tok].append(pos)

        if not positions:
            scores[doc_id] = 0.0
            continue

        # ── baseline: weighted overlap (BIM-style IDF) ──────────────────
        baseline = sum(idf.get(t, 0.0) for t in positions)

        # ── proximity score: sliding window ─────────────────────────────
        doc_len = len(tokens)
        prox_score = 0.0

        if doc_len > 0 and len(query_terms) > 1:
            # For each position of any query term, open a window and score it
            all_positions = sorted(
                (pos, t) for t, plist in positions.items() for pos in plist
            )
            # Use a two-pointer window
            left = 0
            window_terms = defaultdict(int)
            for right, _ in all_positions:
                pass  # just to get the range

            # Slide the window token by token
            # Build a flat list of (position, term) for all query term hits
            hits = sorted(
                (pos, t) for t, plist in positions.items() for pos in plist
            )
            l = 0
            window_counts = defaultdict(int)
            for r in range(len(hits)):
                rpos, rterm = hits[r]
                window_counts[rterm] += 1
                # shrink from left while window span > window size
                while rpos - hits[l][0] >= window:
                    lterm = hits[l][1]
                    window_counts[lterm] -= 1
                    if window_counts[lterm] == 0:
                        del window_counts[lterm]
                    l += 1
                # score this window
                distinct_in_window = len(window_counts)
                total_qt = len(query_terms)
                if distinct_in_window > 1:   # proximity only matters for 2+ terms
                    coverage = distinct_in_window / total_qt
                    # weight by sum of IDF of terms in window
                    idf_sum = sum(idf.get(t, 0.0) for t in window_counts)
                    prox_score = max(prox_score, coverage * coverage * idf_sum)

        # ── final score ──────────────────────────────────────────────────
        scores[doc_id] = (1 - alpha) * baseline + alpha * prox_score

    return scores


def proximal_explain(index, terms, doc_id, window=10):
    """Return the best proximity window for a given doc — used by the UI
    to show *which terms appeared close together* and at what positions.

    Returns dict with keys: best_window_terms, positions, window_size, span
    """
    from preprocess import preprocess as _preprocess

    qt_set = set(terms)
    doc = index.docs.get(doc_id)
    if not doc:
        return {}

    tokens = _preprocess(doc["title"] + " " + doc["text"])
    positions = defaultdict(list)
    for pos, tok in enumerate(tokens):
        if tok in qt_set:
            positions[tok].append(pos)

    if not positions:
        return {"best_window_terms": [], "positions": {}, "window_size": window}

    hits = sorted((pos, t) for t, plist in positions.items() for pos in plist)
    best = {"terms": set(), "start": 0, "end": 0}
    l = 0
    window_counts = defaultdict(int)

    for r in range(len(hits)):
        rpos, rterm = hits[r]
        window_counts[rterm] += 1
        while rpos - hits[l][0] >= window:
            lterm = hits[l][1]
            window_counts[lterm] -= 1
            if window_counts[lterm] == 0:
                del window_counts[lterm]
            l += 1
        if len(window_counts) > len(best["terms"]):
            best = {
                "terms": set(window_counts.keys()),
                "start": hits[l][0],
                "end":   rpos,
            }

    return {
        "best_window_terms": sorted(best["terms"]),
        "positions":         {t: positions[t] for t in qt_set if t in positions},
        "window_size":       window,
        "span":              best["end"] - best["start"] + 1,
    }


# ─────────────────────────────────────────────
#  Registry
# ─────────────────────────────────────────────
MODELS = {
    "tfidf":      tfidf_scores,
    "bm25":       bm25_scores,
    "boolean":    boolean_scores,
    "overlap":    overlap_scores,
    "nonoverlap": lambda idx, terms: {d: v["score"] for d, v in nonoverlap_scores(idx, terms).items()},
    "bim":        bim_scores,
    "proximal":   proximal_scores,
}


def rank(index, terms, model="tfidf", **kwargs):
    """Unified ranking entry point. Returns {doc_id: score}."""
    fn = MODELS.get(model, tfidf_scores)
    return fn(index, terms, **kwargs)
