"""HTTP server: serves the frontend and a JSON API.

    python backend/app.py            ->  http://localhost:8000
    python backend/app.py --reindex  ->  force-rebuild the index

Endpoints
---------
GET  /search   ?q=...&model=tfidf|bm25|boolean|overlap|nonoverlap|bim
               &mode=any|all|not  &k=10
GET  /doc      ?id=<int>
GET  /stats
GET  /models                       list available models with descriptions
GET  /metrics                      all stored evaluation runs
GET  /metrics/best?metric=mrr      name of the best model for a metric
POST /evaluate ?model=...&k=...    run evaluation on built-in test queries
               Body (optional JSON): [{"query":..., "relevant":[id,...]}, ...]
"""
import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from engine import SearchEngine
from indexer import SUPPORTED_EXTENSIONS, load_or_build
from metrics import MetricsStore, evaluate_model

ROOT       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR   = os.path.join(ROOT, "data")
INDEX_PATH = os.path.join(ROOT, "index", "index.json")
FRONTEND   = os.path.join(ROOT, "frontend", "index.html")
METRICS_DIR = os.path.join(ROOT, "metrics")
METRICS_JSON    = os.path.join(METRICS_DIR, "metrics.json")
METRICS_SUMMARY = os.path.join(METRICS_DIR, "metrics_summary.txt")

engine       = None
metrics_store = None

VALID_MODELS = {"tfidf", "bm25", "boolean", "overlap", "nonoverlap", "bim", "proximal"}
VALID_MODES  = {"any", "all", "not"}

MODEL_DESCRIPTIONS = {
    "tfidf":      "TF-IDF cosine similarity (Vector Space Model)",
    "bm25":       "Okapi BM25 – best lexical ranker; handles length and tf saturation",
    "boolean":    "Boolean AND/OR/NOT – exact set matching, no ranking",
    "overlap":    "Overlap model |Q∩D| – keyword overlap count, equal term weights",
    "nonoverlap": "Non-overlap model – like Overlap but also shows missing query terms",
    "bim":        "Binary Independence Model – probabilistic, Robertson-Sparck Jones weights",
    "proximal":   "Proximal Nodes Model – rewards documents where query terms appear close together",
}

# Built-in demo evaluation queries (used when POST /evaluate has no body)
DEMO_QUERIES = [
    {"query": "inverted index postings list",    "relevant": [2]},
    {"query": "TF-IDF weighting cosine",         "relevant": [6, 8]},
    {"query": "BM25 ranking function",           "relevant": [7]},
    {"query": "boolean retrieval model",         "relevant": [9]},
    {"query": "precision recall evaluation",     "relevant": [10]},
    {"query": "web crawling",                    "relevant": [11]},
    {"query": "PageRank link analysis",          "relevant": [12]},
    {"query": "semantic search embeddings",      "relevant": [14]},
    {"query": "vector databases FAISS",          "relevant": [17]},
    {"query": "natural language processing NLP", "relevant": [21]},
    {"query": "query processing optimization",   "relevant": [28]},
    {"query": "search algorithm hash table trie","relevant": [26]},
]


class Handler(BaseHTTPRequestHandler):
    # ── helpers ──────────────────────────────
    def _send(self, status, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length else b""

    # ── routing ──────────────────────────────
    def do_GET(self):
        url    = urlparse(self.path)
        params = {k: v[0] for k, v in parse_qs(url.query).items()}

        # ── frontend ──
        if url.path in ("/", "/index.html"):
            with open(FRONTEND, "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")

        # ── search ──
        if url.path == "/search":
            query = params.get("q", "").strip()[:200]
            model = params.get("model", "tfidf")
            mode  = params.get("mode", "any")
            try:
                k = max(1, min(int(params.get("k", 10)), 50))
            except ValueError:
                k = 10

            if model not in VALID_MODELS:
                return self._send(400, {"error": f"model must be one of {sorted(VALID_MODELS)}"})
            if mode not in VALID_MODES:
                return self._send(400, {"error": f"mode must be one of {sorted(VALID_MODES)}"})
            if not query:
                return self._send(400, {"error": "Missing query parameter q"})

            relevant_raw = params.get("relevant", "")
            try:
                relevant_ids = [int(x) for x in relevant_raw.split(",") if x.strip()]
            except ValueError:
                relevant_ids = []

            try:
                window = max(2, min(int(params.get("window", 10)), 50))
            except ValueError:
                window = 10

            return self._send(200, engine.search(query, model, mode, k,
                                                  relevant_ids=relevant_ids or None,
                                                  window=window))

        # ── single document ──
        if url.path == "/doc":
            try:
                doc = engine.document(int(params.get("id", "")))
            except ValueError:
                doc = None
            if not doc:
                return self._send(404, {"error": "Document not found"})
            return self._send(200, doc)

        # ── collection stats ──
        if url.path == "/stats":
            idx = engine.index
            file_types = {}
            for d in idx.docs.values():
                ft = d.get("file_type", "txt")
                file_types[ft] = file_types.get(ft, 0) + 1
            return self._send(200, {
                "documents":       idx.n_docs,
                "terms":           len(idx.postings),
                "avg_doc_length":  round(idx.avg_len, 1),
                "supported_types": list(SUPPORTED_EXTENSIONS),
                "file_types":      file_types,
            })

        # ── model list ──
        if url.path == "/models":
            return self._send(200, [
                {"id": m, "description": MODEL_DESCRIPTIONS[m]}
                for m in sorted(VALID_MODELS)
            ])

        # ── stored metrics ──
        if url.path == "/metrics":
            return self._send(200, metrics_store.load_all())

        # ── best model ──
        if url.path == "/metrics/best":
            metric = params.get("metric", "mrr")
            best   = metrics_store.best_model(metric=metric)
            return self._send(200, {"metric": metric, "best_model": best})

        self._send(404, {"error": "Not found"})

    def do_POST(self):
        url    = urlparse(self.path)
        params = {k: v[0] for k, v in parse_qs(url.query).items()}

        # ── evaluate a model ──
        if url.path == "/evaluate":
            model = params.get("model", "bm25")
            try:
                k = max(1, min(int(params.get("k", 10)), 50))
            except ValueError:
                k = 10
            if model not in VALID_MODELS:
                return self._send(400, {"error": f"model must be one of {sorted(VALID_MODELS)}"})

            body = self._read_body()
            if body.strip():
                try:
                    queries = json.loads(body)
                except json.JSONDecodeError:
                    return self._send(400, {"error": "Invalid JSON body"})
            else:
                queries = DEMO_QUERIES

            result = evaluate_model(engine, queries, model=model, k=k)
            saved  = metrics_store.save(result)
            return self._send(200, saved)

        self._send(404, {"error": "Not found"})

    def do_OPTIONS(self):   # CORS pre-flight
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} {fmt % args}")


def main():
    global engine, metrics_store
    parser = argparse.ArgumentParser(description="IR Search Engine")
    parser.add_argument("--port",    type=int, default=8000)
    parser.add_argument("--reindex", action="store_true", help="Rebuild index from data/")
    args = parser.parse_args()

    os.makedirs(METRICS_DIR, exist_ok=True)
    metrics_store = MetricsStore(METRICS_JSON, METRICS_SUMMARY)

    index  = load_or_build(DATA_DIR, INDEX_PATH, force=args.reindex)
    engine = SearchEngine(index)

    print(f"Indexed {index.n_docs} documents  |  {len(index.postings)} unique terms")
    print(f"Supported file types: {', '.join(SUPPORTED_EXTENSIONS)}")
    print(f"Models: {', '.join(sorted(VALID_MODELS))}")
    print(f"Open http://localhost:{args.port}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
