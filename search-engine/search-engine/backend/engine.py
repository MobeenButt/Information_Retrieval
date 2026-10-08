"""SearchEngine: query -> text processing -> index lookup -> ranking -> results."""
import html
import re
import time

from preprocess import STOPWORDS, analyze, stem
from ranker import MODELS, rank

_WORD = re.compile(r"[A-Za-z0-9]+")


def make_snippet(text, qterms, span=30):
    """Short excerpt around the first query term, with matches wrapped in <mark>."""
    words = list(_WORD.finditer(text))
    if not words:
        return ""
    qset = set(qterms)
    is_hit = lambda w: w.lower() not in STOPWORDS and stem(w.lower()) in qset
    first = next((i for i, m in enumerate(words) if is_hit(m.group())), 0)
    lo = max(0, first - 6)
    hi = min(len(words) - 1, lo + span)
    piece = text[words[lo].start(): words[hi].end()]
    out = []
    for part in re.split(r"([A-Za-z0-9]+)", piece):
        safe = html.escape(part)
        out.append(f"<mark>{safe}</mark>" if _WORD.fullmatch(part) and is_hit(part) else safe)
    return ("… " if lo > 0 else "") + "".join(out) + (" …" if hi < len(words) - 1 else "")


class SearchEngine:
    def __init__(self, index):
        self.index = index

    def search(self, query, model="tfidf", mode="any", k=10):
        start = time.perf_counter()
        idx = self.index
        stages = analyze(query)
        terms = stages["stems"]
        unique = list(dict.fromkeys(terms))

        lookups = [{"term": t, "df": idx.df(t), "docs": sorted(idx.postings.get(t, {}))}
                   for t in unique]
        scores = rank(idx, terms, model if model in MODELS else "tfidf")
        if mode == "all" and unique:  # every query term must be present (boolean AND)
            allowed = set.intersection(*(set(idx.postings.get(t, {})) for t in unique))
            scores = {d: s for d, s in scores.items() if d in allowed}

        ordered = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
        hits = []
        for doc_id, score in ordered[:k]:
            doc = idx.docs[doc_id]
            hits.append({
                "id": doc_id,
                "title": doc["title"],
                "score": round(score, 4),
                "snippet": make_snippet(doc["text"], unique),
                "matched": [t for t in unique if doc_id in idx.postings.get(t, {})],
            })
        return {
            "query": query,
            "trace": {**stages, "lookups": lookups},
            "total": len(ordered),
            "hits": hits,
            "model": model,
            "mode": mode,
            "took_ms": round((time.perf_counter() - start) * 1000, 2),
        }

    def document(self, doc_id):
        return self.index.docs.get(doc_id)
