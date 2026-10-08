"""HTTP server: serves the frontend and a small JSON API (standard library only).

    python backend/app.py            ->  http://localhost:8000
    GET /search?q=...&model=tfidf|bm25&mode=any|all&k=10
    GET /doc?id=3
    GET /stats
"""
import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from engine import SearchEngine
from indexer import load_or_build

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
INDEX_PATH = os.path.join(ROOT, "index", "index.json")
FRONTEND = os.path.join(ROOT, "frontend", "index.html")

engine = None


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        params = {k: v[0] for k, v in parse_qs(url.query).items()}

        if url.path in ("/", "/index.html"):
            with open(FRONTEND, "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")

        if url.path == "/search":
            query = params.get("q", "").strip()[:200]
            model = params.get("model", "tfidf")
            mode = params.get("mode", "any")
            try:
                k = max(1, min(int(params.get("k", 10)), 50))
            except ValueError:
                k = 10
            if model not in ("tfidf", "bm25") or mode not in ("any", "all"):
                return self._send(400, {"error": "model must be tfidf|bm25 and mode any|all"})
            if not query:
                return self._send(400, {"error": "Missing query parameter q"})
            return self._send(200, engine.search(query, model, mode, k))

        if url.path == "/doc":
            try:
                doc = engine.document(int(params.get("id", "")))
            except ValueError:
                doc = None
            if not doc:
                return self._send(404, {"error": "Document not found"})
            return self._send(200, doc)

        if url.path == "/stats":
            idx = engine.index
            return self._send(200, {"documents": idx.n_docs, "terms": len(idx.postings),
                                    "avg_doc_length": round(idx.avg_len, 1)})

        self._send(404, {"error": "Not found"})

    def log_message(self, fmt, *args):  # quieter console
        print(f"{self.address_string()} {fmt % args}")


def main():
    global engine
    parser = argparse.ArgumentParser(description="Mini search engine")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reindex", action="store_true", help="rebuild the index from data/")
    args = parser.parse_args()

    index = load_or_build(DATA_DIR, INDEX_PATH, force=args.reindex)
    engine = SearchEngine(index)
    print(f"Indexed {index.n_docs} documents, {len(index.postings)} unique terms.")
    print(f"Open http://localhost:{args.port}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
