"""IR evaluation metrics and persistent metric storage.

Metrics computed
----------------
precision_at_k   Fraction of top-k results that are relevant
recall_at_k      Fraction of all relevant items in top-k
f1_at_k          Harmonic mean of P@k and R@k
mrr              Mean Reciprocal Rank (first relevant result)
ndcg_at_k        Normalised Discounted Cumulative Gain
average_precision AP for a single query; mAP is the mean over queries

Persistence
-----------
MetricsStore     Appends evaluation runs to metrics.json and writes a
                 human-readable summary to metrics_summary.txt.
"""
import json
import math
import os
import time
from datetime import datetime


# ─────────────────────────────────────────────
#  Core metric functions
# ─────────────────────────────────────────────

def precision_at_k(ranked_ids, relevant_ids, k):
    """Fraction of the top-k results that are relevant."""
    top_k = ranked_ids[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for d in top_k if d in relevant_ids)
    return hits / k


def recall_at_k(ranked_ids, relevant_ids, k):
    """Fraction of all relevant items that appear in the top-k results."""
    if not relevant_ids:
        return 0.0
    top_k = ranked_ids[:k]
    hits = sum(1 for d in top_k if d in relevant_ids)
    return hits / len(relevant_ids)


def f1_at_k(ranked_ids, relevant_ids, k):
    """Harmonic mean of P@k and R@k."""
    p = precision_at_k(ranked_ids, relevant_ids, k)
    r = recall_at_k(ranked_ids, relevant_ids, k)
    if p + r == 0:
        return 0.0
    return 2 * p * r / (p + r)


def reciprocal_rank(ranked_ids, relevant_ids):
    """1 / rank of the first relevant result; 0 if none found."""
    for i, doc_id in enumerate(ranked_ids, 1):
        if doc_id in relevant_ids:
            return 1.0 / i
    return 0.0


def average_precision(ranked_ids, relevant_ids):
    """Average precision (AP) for a single query."""
    if not relevant_ids:
        return 0.0
    hits = 0
    ap = 0.0
    for i, doc_id in enumerate(ranked_ids, 1):
        if doc_id in relevant_ids:
            hits += 1
            ap += hits / i
    return ap / len(relevant_ids)


def dcg_at_k(ranked_ids, relevant_ids, k):
    """Discounted Cumulative Gain at k (binary relevance: 1 if relevant, else 0)."""
    dcg = 0.0
    for i, doc_id in enumerate(ranked_ids[:k], 1):
        if doc_id in relevant_ids:
            dcg += 1.0 / math.log2(i + 1)
    return dcg


def ndcg_at_k(ranked_ids, relevant_ids, k):
    """Normalised DCG at k."""
    ideal_ranked = list(relevant_ids)[:k]   # best possible ordering
    ideal = dcg_at_k(ideal_ranked, relevant_ids, k)
    if ideal == 0:
        return 0.0
    return dcg_at_k(ranked_ids, relevant_ids, k) / ideal


def compute_all(ranked_ids, relevant_ids, k=10):
    """Return a dict with every metric for one query."""
    rel_set = set(relevant_ids)
    return {
        f"precision@{k}":  round(precision_at_k(ranked_ids, rel_set, k), 4),
        f"recall@{k}":     round(recall_at_k(ranked_ids, rel_set, k), 4),
        f"f1@{k}":         round(f1_at_k(ranked_ids, rel_set, k), 4),
        "mrr":             round(reciprocal_rank(ranked_ids, rel_set), 4),
        "ap":              round(average_precision(ranked_ids, rel_set), 4),
        f"ndcg@{k}":       round(ndcg_at_k(ranked_ids, rel_set, k), 4),
    }


def mean_metrics(per_query_list):
    """Average a list of per-query metric dicts into a single mean-metric dict."""
    if not per_query_list:
        return {}
    keys = per_query_list[0].keys()
    result = {}
    for k in keys:
        vals = [q[k] for q in per_query_list if k in q]
        result[k] = round(sum(vals) / len(vals), 4) if vals else 0.0
    return result


# ─────────────────────────────────────────────
#  Evaluate a model across multiple queries
# ─────────────────────────────────────────────

def evaluate_model(engine, queries_with_relevance, model, k=10):
    """Run *model* on every query and return aggregated metrics.

    Parameters
    ----------
    engine                 SearchEngine instance
    queries_with_relevance list of {"query": str, "relevant": [doc_id, ...]}
    model                  one of tfidf | bm25 | boolean | overlap | nonoverlap | bim
    k                      cutoff for ranked metrics

    Returns
    -------
    dict with keys: model, k, mean_metrics, per_query, took_ms
    """
    per_query = []
    start = time.perf_counter()

    for item in queries_with_relevance:
        query   = item["query"]
        rel_ids = set(item["relevant"])
        result  = engine.search(query, model=model, k=max(k, 20))
        ranked  = [h["id"] for h in result["hits"]]
        m       = compute_all(ranked, rel_ids, k)
        m["query"] = query
        per_query.append(m)

    took = round((time.perf_counter() - start) * 1000, 2)
    return {
        "model":        model,
        "k":            k,
        "mean_metrics": mean_metrics([{kk: v for kk, v in q.items() if kk != "query"}
                                      for q in per_query]),
        "per_query":    per_query,
        "took_ms":      took,
    }


# ─────────────────────────────────────────────
#  Persistent metric storage
# ─────────────────────────────────────────────

class MetricsStore:
    """Append evaluation results to a JSON file and a human-readable summary."""

    def __init__(self, json_path, summary_path=None):
        self.json_path    = json_path
        self.summary_path = summary_path or os.path.splitext(json_path)[0] + "_summary.txt"
        os.makedirs(os.path.dirname(json_path), exist_ok=True)

    def _load_all(self):
        if os.path.exists(self.json_path):
            with open(self.json_path, encoding="utf-8") as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return []
        return []

    def save(self, eval_result):
        """Append one evaluation result dict and refresh the summary file."""
        all_results = self._load_all()
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            **eval_result,
        }
        all_results.append(entry)
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2)
        self._write_summary(all_results)
        return entry

    def _write_summary(self, all_results):
        lines = [
            "IR Model Evaluation Summary",
            "=" * 60,
            f"Generated: {datetime.utcnow().isoformat()}Z",
            f"Total evaluation runs: {len(all_results)}",
            "",
        ]

        # Group by model, keep the latest run per model
        latest = {}
        for r in all_results:
            latest[r["model"]] = r

        # Header row
        col_width = 14
        metric_keys = []
        for r in latest.values():
            metric_keys = list(r.get("mean_metrics", {}).keys())
            break

        header = f"{'Model':<12}" + "".join(f"{k:>{col_width}}" for k in metric_keys)
        lines.append(header)
        lines.append("-" * len(header))

        for model, r in sorted(latest.items()):
            mm = r.get("mean_metrics", {})
            row = f"{model:<12}" + "".join(
                f"{mm.get(k, 0.0):>{col_width}.4f}" for k in metric_keys
            )
            lines.append(row)

        lines += ["", "─" * 60, "", "Per-run history (newest first):", ""]
        for r in reversed(all_results):
            mm = r.get("mean_metrics", {})
            lines.append(f"[{r['timestamp']}]  model={r['model']}  k={r['k']}")
            for k, v in mm.items():
                lines.append(f"    {k:<20} {v:.4f}")
            lines.append("")

        with open(self.summary_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def load_latest(self, model=None):
        """Return the most recent evaluation result, optionally filtered by model."""
        all_results = self._load_all()
        if model:
            all_results = [r for r in all_results if r.get("model") == model]
        return all_results[-1] if all_results else None

    def load_all(self):
        return self._load_all()

    def best_model(self, metric="mrr"):
        """Return the model name with the highest mean value for *metric*."""
        all_results = self._load_all()
        if not all_results:
            return None
        latest = {}
        for r in all_results:
            latest[r["model"]] = r
        best = max(latest.values(),
                   key=lambda r: r.get("mean_metrics", {}).get(metric, -1))
        return best.get("model")
