"""SearchEngine: query -> text processing -> index lookup -> ranking -> results.

Supported ranking models
------------------------
tfidf       TF-IDF cosine similarity  (Vector Space Model)
bm25        Okapi BM25
boolean     AND / OR / NOT set matching (unranked, returns score=1)
overlap     Keyword overlap |Q ∩ D|
nonoverlap  Same score as overlap + missing-terms explanation
bim         Binary Independence Model (Robertson-Sparck Jones)
proximal    Proximal Nodes Model      (positional proximity-based ranking)
"""
import html
import re
import time

from preprocess import STOPWORDS, analyze, stem
from ranker import MODELS, boolean_search, nonoverlap_scores, proximal_explain, rank

_WORD = re.compile(r"[A-Za-z0-9]+")

_BOOL_MODES = {"any": "or", "all": "and", "not": "not", "or": "or", "and": "and"}


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
        out.append(f"<mark>{safe}</mark>"
                   if _WORD.fullmatch(part) and is_hit(part) else safe)
    return ("… " if lo > 0 else "") + "".join(out) + (" …" if hi < len(words) - 1 else "")


class SearchEngine:
    def __init__(self, index):
        self.index = index

    def search(self, query, model="tfidf", mode="any", k=10,
               relevant_ids=None, window=10):
        """
        Parameters
        ----------
        query        : raw query string
        model        : tfidf|bm25|boolean|overlap|nonoverlap|bim|proximal
        mode         : for boolean → any/all/not; for ranked → any (default)
        k            : number of results to return
        relevant_ids : doc_id list for BIM relevance feedback
        window       : token window size for proximal model (default 10)
        """
        start = time.perf_counter()
        idx   = self.index

        stages = analyze(query)
        terms  = stages["stems"]
        unique = list(dict.fromkeys(terms))

        lookups = [
            {"term": t, "df": idx.df(t), "docs": sorted(idx.postings.get(t, {}))}
            for t in unique
        ]

        missing_map  = {}
        proximal_map = {}

        if model == "nonoverlap":
            no_data = nonoverlap_scores(idx, terms)
            scores  = {d: v["score"] for d, v in no_data.items() if v["score"] > 0}
            missing_map = {d: v["missing"] for d, v in no_data.items()}

        elif model == "boolean":
            bool_mode = _BOOL_MODES.get(mode, "or")
            matched   = boolean_search(idx, terms, mode=bool_mode)
            scores    = {doc_id: 1.0 for doc_id in matched}

        elif model == "bim":
            scores = rank(idx, terms, model="bim", relevant_ids=relevant_ids or [])

        elif model == "proximal":
            scores = rank(idx, terms, model="proximal", window=window)
            # build proximity explanations for top results
            ordered_preview = sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:k]
            for doc_id, _ in ordered_preview:
                proximal_map[doc_id] = proximal_explain(idx, unique, doc_id, window)

        else:
            scores = rank(idx, terms, model if model in MODELS else "tfidf")
            if mode == "all" and unique:
                allowed = set.intersection(
                    *(set(idx.postings.get(t, {})) for t in unique)
                )
                scores = {d: s for d, s in scores.items() if d in allowed}

        ordered = sorted(scores.items(), key=lambda x: (-x[1], x[0]))

        hits = []
        for doc_id, score in ordered[:k]:
            doc = idx.docs.get(doc_id)
            if doc is None:
                continue
            hit = {
                "id":        doc_id,
                "title":     doc["title"],
                "score":     round(score, 4),
                "snippet":   make_snippet(doc["text"], unique),
                "matched":   [t for t in unique if doc_id in idx.postings.get(t, {})],
                "file_type": doc.get("file_type", "txt"),
                "source":    doc.get("source", ""),
            }
            if model == "nonoverlap":
                hit["missing"] = missing_map.get(doc_id, [])
            if model == "proximal" and doc_id in proximal_map:
                hit["proximity"] = proximal_map[doc_id]
            hits.append(hit)

        return {
            "query":    query,
            "trace":    {**stages, "lookups": lookups},
            "total":    len(ordered),
            "hits":     hits,
            "model":    model,
            "mode":     mode,
            "took_ms":  round((time.perf_counter() - start) * 1000, 2),
        }

    def document(self, doc_id):
        return self.index.docs.get(doc_id)
