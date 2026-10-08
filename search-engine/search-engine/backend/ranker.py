"""Ranking models. Each returns {doc_id: score} for documents sharing a term with the query."""
import math
from collections import Counter, defaultdict


def tfidf_scores(index, terms):
    """TF-IDF with cosine-style length normalisation.

    weight(term, doc) = (1 + log tf) * idf        score = sum(query_w * doc_w) / |doc vector|
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


def bm25_scores(index, terms, k1=1.5, b=0.75):
    """Okapi BM25: saturating term frequency + document length normalisation."""
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


MODELS = {"tfidf": tfidf_scores, "bm25": bm25_scores}


def rank(index, terms, model="tfidf"):
    return MODELS[model](index, terms)
