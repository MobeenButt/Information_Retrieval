"""IR evaluation (Week 3).

Computes Precision@k, Recall@k, F1, Average Precision, MRR and nDCG for
every model across the relevance-judged queries, and prints a Markdown
comparison table. The judgments live in data/relevance_judgments.json.
"""
from __future__ import annotations

import json
import math
import os
from typing import Dict, List, Set

from boolean_model import parse_and_execute
from probabilistic_models import bim_search, bm25_search
from structured_retrieval import (field_bm25_search, non_overlapped_lists,
                                  overlapped_lists, proximal_nodes)
from vector_space_model import vsm_search


# ─────────────────────────────────────────────
#  Week 3 - Evaluation
# ─────────────────────────────────────────────
_JUDGMENTS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "relevance_judgments.json"
)

MODELS_TO_EVALUATE = [
    "boolean", "vsm", "bm25", "bim",
    "overlap", "nonoverlap", "proximal", "field_bm25",
]


# ── core metrics ─────────────────────────────
def precision_at_k(ranked: List[int], relevant: Set[int], k: int) -> float:
    top = ranked[:k]
    return (sum(1 for d in top if d in relevant) / k) if top else 0.0


def recall_at_k(ranked: List[int], relevant: Set[int], k: int) -> float:
    if not relevant:
        return 0.0
    return sum(1 for d in ranked[:k] if d in relevant) / len(relevant)


def f1_at_k(ranked: List[int], relevant: Set[int], k: int) -> float:
    p = precision_at_k(ranked, relevant, k)
    r = recall_at_k(ranked, relevant, k)
    return (2 * p * r / (p + r)) if (p + r) else 0.0


def average_precision(ranked: List[int], relevant: Set[int]) -> float:
    if not relevant:
        return 0.0
    hits, ap = 0, 0.0
    for i, d in enumerate(ranked, 1):
        if d in relevant:
            hits += 1
            ap += hits / i
    return ap / len(relevant)


def reciprocal_rank(ranked: List[int], relevant: Set[int]) -> float:
    for i, d in enumerate(ranked, 1):
        if d in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked: List[int], relevant: Set[int], k: int) -> float:
    dcg = sum(1.0 / math.log2(i + 1) for i, d in enumerate(ranked[:k], 1) if d in relevant)
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, min(k, len(relevant)) + 1))
    return (dcg / ideal) if ideal else 0.0


# ── model -> ranked doc ids ──────────────────
def _ranked_ids(model: str, query: str, index, k: int = 50) -> List[int]:
    if model == "boolean":
        ids, _ = parse_and_execute(query, index)
        return sorted(ids)
    if model == "vsm":
        return [h["id"] for h in vsm_search(query, index, top_k=k)]
    if model == "bm25":
        return [h["id"] for h in bm25_search(query, index, top_k=k)]
    if model == "bim":
        return [h["id"] for h in bim_search(query, index, top_k=k)]
    if model == "overlap":
        return [h["id"] for h in overlapped_lists(query, index)]
    if model == "nonoverlap":
        return [h["id"] for h in non_overlapped_lists(query, index)]
    if model == "proximal":
        return [h["id"] for h in proximal_nodes(query, index, top_k=k)]
    if model == "field_bm25":
        return [h["id"] for h in field_bm25_search(query, index, top_k=k)]
    return []


def load_relevance_judgments(path: str = _JUDGMENTS_PATH) -> List[Dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def evaluate_all_models(index) -> Dict[str, Dict[str, Dict[str, float]]]:
    """Run every model on every judged query.

    Returns nested dict: ``{model: {query: {metric: value}}}``.
    """
    judgments = load_relevance_judgments()
    k = 5
    results: Dict[str, Dict[str, Dict[str, float]]] = {}
    for model in MODELS_TO_EVALUATE:
        results[model] = {}
        for item in judgments:
            query = item["query"]
            relevant = set(item["relevant"])
            ranked = _ranked_ids(model, query, index, k=k)
            results[model][query] = {
                "precision@5": round(precision_at_k(ranked, relevant, k), 4),
                "recall@5": round(recall_at_k(ranked, relevant, k), 4),
                "f1@5": round(f1_at_k(ranked, relevant, k), 4),
                "ap": round(average_precision(ranked, relevant), 4),
                "mrr": round(reciprocal_rank(ranked, relevant), 4),
                "ndcg@5": round(ndcg_at_k(ranked, relevant, k), 4),
            }
    return results


def print_comparison_table(results: Dict[str, Dict[str, Dict[str, float]]]) -> str:
    """Markdown table: rows = models, cols = mean P@5, R@5, F1@5, AP, MRR."""
    cols = ["precision@5", "recall@5", "f1@5", "ap", "mrr"]
    lines = [
        "| Model | P@5 | R@5 | F1@5 | AP | MRR |",
        "|---|---|---|---|---|---|",
    ]
    for model, per_query in results.items():
        qs = list(per_query.values())
        means = {c: round(sum(q[c] for q in qs) / len(qs), 4) for c in cols}
        lines.append(
            f"| {model} | {means['precision@5']} | {means['recall@5']} | "
            f"{means['f1@5']} | {means['ap']} | {means['mrr']} |"
        )
    return "\n".join(lines)
