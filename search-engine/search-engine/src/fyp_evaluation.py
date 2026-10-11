"""FYP mock-data evaluation pipeline.

Runs all IR models against the FYP corpus (BEIR format) and computes
Precision@k, Recall@k, F1@k, MRR, MAP, nDCG@k for every model.
Saves results to metrics/fyp_metrics.json.

Usage
-----
    python src/fyp_evaluation.py          # run all models, print & save
    python src/fyp_evaluation.py --k 10   # override top-k (default 10)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from collections import defaultdict
from typing import Dict, List, Set, Tuple

# ── model imports ──────────────────────────────────────────────
from boolean_model import boolean_search
from fyp_loader import build_fyp_index, load_qrels, load_queries, translate_results
from probabilistic_models import bim_search, bm25_search
from structured_retrieval import (field_bm25_search, non_overlapped_lists,
                                  overlapped_lists, proximal_nodes)
from vector_space_model import vsm_search

_HERE        = os.path.dirname(os.path.abspath(__file__))
METRICS_DIR  = os.path.join(_HERE, "..", "metrics")
OUTPUT_PATH  = os.path.join(METRICS_DIR, "fyp_metrics.json")
os.makedirs(METRICS_DIR, exist_ok=True)


# ══════════════════════════════════════════════════════════════
#  Metric functions
# ══════════════════════════════════════════════════════════════

def precision_at_k(ranked: List[str], relevant: Set[str], k: int) -> float:
    top = ranked[:k]
    return sum(1 for d in top if d in relevant) / k if top else 0.0

def recall_at_k(ranked: List[str], relevant: Set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return sum(1 for d in ranked[:k] if d in relevant) / len(relevant)

def f1_at_k(ranked: List[str], relevant: Set[str], k: int) -> float:
    p = precision_at_k(ranked, relevant, k)
    r = recall_at_k(ranked, relevant, k)
    return (2 * p * r / (p + r)) if p + r else 0.0

def mrr(ranked: List[str], relevant: Set[str]) -> float:
    for i, d in enumerate(ranked, 1):
        if d in relevant:
            return 1.0 / i
    return 0.0

def average_precision(ranked: List[str], relevant: Set[str]) -> float:
    if not relevant:
        return 0.0
    hits, ap = 0, 0.0
    for i, d in enumerate(ranked, 1):
        if d in relevant:
            hits += 1
            ap += hits / i
    return ap / len(relevant)

def ndcg_at_k(ranked: List[str], qrels_for_query: Dict[str, int], k: int) -> float:
    """nDCG using graded relevance scores from qrels (0/1/2)."""
    def dcg(ids):
        return sum(
            qrels_for_query.get(d, 0) / math.log2(i + 1)
            for i, d in enumerate(ids, 1)
        )
    ideal = sorted(qrels_for_query.values(), reverse=True)[:k]
    ideal_ids = [f"__ideal_{i}__" for i in range(len(ideal))]
    ideal_qrels = {f"__ideal_{i}__": v for i, v in enumerate(ideal)}
    idcg = dcg(ideal_ids[:k]) if ideal else 0.0
    # recompute ideal dcg directly
    idcg = sum(v / math.log2(i + 1) for i, v in enumerate(ideal, 1))
    return dcg(ranked[:k]) / idcg if idcg else 0.0

def compute_metrics(ranked: List[str], relevant: Set[str],
                    qrels_for_query: Dict[str, int], k: int) -> Dict[str, float]:
    return {
        f"P@{k}":    round(precision_at_k(ranked, relevant, k), 4),
        f"R@{k}":    round(recall_at_k(ranked, relevant, k), 4),
        f"F1@{k}":   round(f1_at_k(ranked, relevant, k), 4),
        "MRR":       round(mrr(ranked, relevant), 4),
        "MAP":       round(average_precision(ranked, relevant), 4),
        f"nDCG@{k}": round(ndcg_at_k(ranked, qrels_for_query, k), 4),
    }

def mean_metrics(per_query: List[Dict[str, float]]) -> Dict[str, float]:
    if not per_query:
        return {}
    keys = per_query[0].keys()
    return {k: round(sum(q[k] for q in per_query) / len(per_query), 4) for k in keys}


# ══════════════════════════════════════════════════════════════
#  Run one model on all queries
# ══════════════════════════════════════════════════════════════

def run_model(model_name: str, idx, id_map: Dict[int, str],
              queries: List[Dict], qrels: Dict[str, Dict[str, int]],
              k: int = 10) -> Dict:
    """Return per-query and mean metrics for one model."""
    per_query_results = []
    per_query_metrics = []
    t0 = time.perf_counter()

    for q in queries:
        qid   = q["_id"]
        qtext = q["text"]

        # ── dispatch to model ──────────────────────────────────
        if model_name == "boolean":
            hits = boolean_search(qtext, idx, top_k=k * 2)
        elif model_name == "bm25":
            hits = bm25_search(qtext, idx, top_k=k * 2)
        elif model_name == "vsm":
            hits = vsm_search(qtext, idx, top_k=k * 2)
        elif model_name == "bim":
            hits = bim_search(qtext, idx, top_k=k * 2)
        elif model_name == "overlap":
            hits = overlapped_lists(qtext, idx)[:k * 2]
        elif model_name == "nonoverlap":
            hits = non_overlapped_lists(qtext, idx)[:k * 2]
        elif model_name == "proximal":
            hits = proximal_nodes(qtext, idx, top_k=k * 2)
        elif model_name == "field_bm25":
            hits = field_bm25_search(qtext, idx, top_k=k * 2)
        else:
            hits = bm25_search(qtext, idx, top_k=k * 2)

        # translate int ids -> original corpus string ids
        hits_translated = translate_results(hits, id_map)
        ranked_corpus_ids = [h["corpus_id"] for h in hits_translated]

        # relevance set: any document with score >= 1
        q_qrels  = qrels.get(qid, {})
        relevant = {cid for cid, score in q_qrels.items() if score >= 1}

        m = compute_metrics(ranked_corpus_ids, relevant, q_qrels, k)
        m["query_id"]   = qid
        m["query_text"] = qtext
        m["num_relevant"] = len(relevant)
        m["retrieved"]  = ranked_corpus_ids[:k]

        per_query_metrics.append(m)
        per_query_results.append({
            "query_id": qid,
            "query_text": qtext,
            "hits": hits_translated[:k],
        })

    took_ms = round((time.perf_counter() - t0) * 1000, 1)

    # separate pure metric dicts (no string keys) for mean computation
    pure = [{k: v for k, v in m.items()
             if k not in ("query_id", "query_text", "num_relevant", "retrieved")}
            for m in per_query_metrics]

    return {
        "model":        model_name,
        "k":            k,
        "took_ms":      took_ms,
        "mean_metrics": mean_metrics(pure),
        "per_query":    per_query_metrics,
        "results":      per_query_results,
    }


# ══════════════════════════════════════════════════════════════
#  Run all models and save
# ══════════════════════════════════════════════════════════════

ALL_MODELS = ["bm25", "vsm", "bim", "boolean", "overlap", "nonoverlap",
              "proximal", "field_bm25"]

def evaluate_all(k: int = 10, force_reindex: bool = False) -> Dict:
    """Run every model and return a summary dict; also save to fyp_metrics.json."""
    print(f"\nBuilding FYP index (force={force_reindex})…")
    idx, id_map = build_fyp_index(force=force_reindex)
    print(f"  {idx.n_docs} documents indexed, {len(idx.postings)} terms")

    queries = load_queries()
    qrels   = load_qrels()
    print(f"  {len(queries)} queries, {sum(len(v) for v in qrels.values())} total judgments\n")

    results_by_model = {}
    summary_rows     = []

    for model in ALL_MODELS:
        print(f"  Running {model}…", end=" ", flush=True)
        r = run_model(model, idx, id_map, queries, qrels, k=k)
        results_by_model[model] = r
        mm = r["mean_metrics"]
        summary_rows.append({"model": model, **mm, "took_ms": r["took_ms"]})
        keys = list(mm.keys())
        vals = "  ".join(f"{kk}={mm[kk]:.4f}" for kk in keys)
        print(f"{r['took_ms']} ms  |  {vals}")

    # find best model by nDCG@k
    ndcg_key  = f"nDCG@{k}"
    mrr_key   = "MRR"
    map_key   = "MAP"
    best_ndcg = max(results_by_model.values(),
                    key=lambda r: r["mean_metrics"].get(ndcg_key, 0))
    best_mrr  = max(results_by_model.values(),
                    key=lambda r: r["mean_metrics"].get(mrr_key, 0))
    best_map  = max(results_by_model.values(),
                    key=lambda r: r["mean_metrics"].get(map_key, 0))

    summary = {
        "corpus_size":   idx.n_docs,
        "num_queries":   len(queries),
        "k":             k,
        "best_by_ndcg":  best_ndcg["model"],
        "best_by_mrr":   best_mrr["model"],
        "best_by_map":   best_map["model"],
        "summary_rows":  summary_rows,
        "by_model":      results_by_model,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\n  Results saved → {OUTPUT_PATH}")
    print(f"\n  BEST MODEL  nDCG@{k}: {best_ndcg['model'].upper()}  "
          f"({best_ndcg['mean_metrics'].get(ndcg_key, 0):.4f})")
    print(f"  BEST MODEL  MRR     : {best_mrr['model'].upper()}  "
          f"({best_mrr['mean_metrics'].get(mrr_key, 0):.4f})")
    print(f"  BEST MODEL  MAP     : {best_map['model'].upper()}  "
          f"({best_map['mean_metrics'].get(map_key, 0):.4f})\n")

    return summary


def load_saved_results() -> Dict | None:
    """Load previously saved FYP evaluation results from disk."""
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            return json.load(f)
    return None


# ── CLI entry point ────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--k",       type=int, default=10)
    parser.add_argument("--reindex", action="store_true")
    args = parser.parse_args()
    evaluate_all(k=args.k, force_reindex=args.reindex)
