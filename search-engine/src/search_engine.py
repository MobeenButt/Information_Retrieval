"""SearchEngine facade: ties every retrieval model behind one ``search`` call.

``SearchEngine(data_path, index_path)`` loads (or builds) the index and exposes
``search(query, model, ...)`` which dispatches to the requested model and returns
a uniform result dict, plus ``pipeline_trace(query)`` for the UI pipeline view.
"""
from __future__ import annotations

import os
import time
from typing import Dict, List, Optional

from boolean_model import boolean_search
from classification_clustering import filter_by_category
from indexing import InvertedIndex
from probabilistic_models import bim_search, bm25_search
from structured_retrieval import (field_bm25_search, non_overlapped_lists,
                                  overlapped_lists, proximal_nodes)
from text_processing import analyze_pipeline, preprocess, remove_stopwords, stem_all, tokenize
from vector_space_model import vsm_search


class SearchEngine:
    """Top-level search interface over the structured document index."""

    def __init__(self, data_path: str = "data/documents.json",
                 index_path: str = "index/structured_index.json") -> None:
        self.data_path = data_path
        self.index_path = index_path
        if data_path.endswith(".json"):
            self.index = InvertedIndex.load_or_build(index_path, json_path=data_path)
        else:
            self.index = InvertedIndex.load_or_build(index_path, folder_path=data_path)

    # ── model dispatch ─────────────────────────
    def _run_model(self, query: str, model: str, fields: Optional[Dict[str, float]],
                   k1: float, b: float, show_math: bool, top_k: int) -> List[Dict]:
        idx = self.index
        if model == "boolean":
            return boolean_search(query, idx, top_k=top_k)
        if model == "vsm":
            return vsm_search(query, idx, top_k=top_k)
        if model == "bm25":
            return bm25_search(query, idx, k1=k1, b=b, top_k=top_k, show_math=show_math)
        if model == "bim":
            return bim_search(query, idx, top_k=top_k)
        if model == "overlap":
            return overlapped_lists(query, idx)
        if model == "nonoverlap":
            return non_overlapped_lists(query, idx)
        if model == "proximal":
            return proximal_nodes(query, idx, top_k=top_k)
        if model == "field_bm25":
            return field_bm25_search(query, idx, field_weights=fields, top_k=top_k)
        # default
        return bm25_search(query, idx, top_k=top_k)

    def search(self, query: str, model: str = "bm25",
               fields: Optional[Dict[str, float]] = None,
               top_k: int = 10, filters: Optional[Dict] = None,
               show_math: bool = False, k1: float = 1.5, b: float = 0.75) -> Dict:
        """Run ``query`` through ``model`` and return a uniform result dict.

        keys: query, model, pipeline, hits, total, took_ms
        """
        start = time.perf_counter()
        idx = self.index
        pipeline = analyze_pipeline(query)
        model = (model or "bm25").lower()

        # fetch all matches so 'total' reflects the full result set
        fetch_k = max(top_k, idx.n_docs)
        hits = self._run_model(query, model, fields, k1, b, show_math, top_k=fetch_k)

        if filters and filters.get("category"):
            hits = filter_by_category(hits, filters["category"])

        total = len(hits)
        hits = hits[:top_k]
        return {
            "query": query,
            "model": model,
            "pipeline": pipeline,
            "hits": hits,
            "total": total,
            "took_ms": round((time.perf_counter() - start) * 1000, 2),
        }

    def pipeline_trace(self, query: str) -> List[Dict]:
        """Return the retrieval pipeline as a list of stage dicts (for the UI)."""
        idx = self.index
        tokens = tokenize(query)
        no_stop = remove_stopwords(tokens)
        stems = stem_all(no_stop)
        lookups = [
            {"term": t, "df": idx.df(t),
             "postings": sorted(idx.postings.get(t, {}).keys())}
            for t in dict.fromkeys(stems)
        ]
        return [
            {"stage": "raw_query", "description": "Original user query", "output": query},
            {"stage": "tokenize", "description": "Lowercase and split into alphanumeric tokens",
             "output": tokens},
            {"stage": "remove_stopwords", "description": "Drop common stop-words",
             "output": no_stop},
            {"stage": "stem", "description": "Porter-style suffix stripping",
             "output": stems},
            {"stage": "index_lookup", "description": "Look up each stem in the inverted index",
             "output": lookups},
        ]
