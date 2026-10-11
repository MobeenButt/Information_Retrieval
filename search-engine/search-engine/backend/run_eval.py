"""Quick evaluation script – run all models and save metrics."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from indexer import build_index
from engine import SearchEngine
from metrics import MetricsStore, evaluate_model

DATA  = os.path.join(os.path.dirname(__file__), '..', 'data')
MDIR  = os.path.join(os.path.dirname(__file__), '..', 'metrics')
os.makedirs(MDIR, exist_ok=True)

idx   = build_index(DATA)
eng   = SearchEngine(idx)
store = MetricsStore(
    os.path.join(MDIR, 'metrics.json'),
    os.path.join(MDIR, 'metrics_summary.txt')
)

TEST_QUERIES = [
    {"query": "inverted index postings list",     "relevant": [2]},
    {"query": "TF-IDF weighting cosine",          "relevant": [6, 8]},
    {"query": "BM25 ranking function",            "relevant": [7]},
    {"query": "boolean retrieval model",          "relevant": [9]},
    {"query": "precision recall evaluation",      "relevant": [10]},
    {"query": "web crawling",                     "relevant": [11]},
    {"query": "PageRank link analysis",           "relevant": [12]},
    {"query": "semantic search embeddings",       "relevant": [14]},
    {"query": "vector databases FAISS",           "relevant": [17]},
    {"query": "natural language processing NLP",  "relevant": [21]},
]

MODELS = ["tfidf", "bm25", "boolean", "overlap", "nonoverlap", "bim", "proximal"]
print("Running evaluation for all models…\n")
print(f"  {'Model':<14} {'MRR':>6} {'nDCG@10':>9} {'P@10':>7} {'R@10':>7}")
print("  " + "-" * 48)

for m in MODELS:
    r  = evaluate_model(eng, TEST_QUERIES, model=m, k=10)
    mm = r["mean_metrics"]
    store.save(r)
    print("  {:<14} {:>6.3f} {:>9.3f} {:>7.3f} {:>7.3f}".format(
        m, mm["mrr"], mm["ndcg@10"], mm["precision@10"], mm["recall@10"]
    ))

best = store.best_model("mrr")
print("\nBest model by MRR:", best)
print("Metrics JSON   :", os.path.join(MDIR, "metrics.json"))
print("Metrics summary:", os.path.join(MDIR, "metrics_summary.txt"))
