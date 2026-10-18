"""BrowseServer — HTTP routing layer for the Browsing and Navigation Module.

Reuses the existing search-engine backend via sys.path injection.
Run with:  python app.py
           run.bat
"""
import sys
import os
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

# --- sys.path injection (backend reuse) ---
ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(ROOT, "..", "search-engine", "backend")
sys.path.insert(0, BACKEND)

from browse import BrowseEngine  # noqa: E402 — import after sys.path injection

ENGINE: BrowseEngine = None  # initialised in main()

PORT = 8080


class Handler(BaseHTTPRequestHandler):
    """HTTP request handler — implemented in Task 7."""

    def _send(self, status: int, body, ctype="application/json; charset=utf-8"):
        """Serialise *body* to JSON, write CORS + content headers, and send."""
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self, path: str):
        """Read *path* from disk and send it as text/html with CORS headers."""
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError:
            self._send(404, {"error": "not found"})
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        """Handle CORS pre-flight requests."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Allow", "GET, OPTIONS")
        self.end_headers()

    def do_GET(self):
        """Route GET requests to the appropriate handler."""
        url = urlparse(self.path)
        params = {k: v[0] for k, v in parse_qs(url.query).items()}

        if url.path in ("/", "/index.html"):
            index_path = os.path.join(ROOT, "index.html")
            return self._send_html(index_path)
        elif url.path == "/api/categories":
            return self._send(200, ENGINE.category_tree())
        elif url.path == "/api/browse":
            cat = params.get("cat", "")
            sub = params.get("sub", "")
            return self._send(200, ENGINE.browse(cat, sub))
        elif url.path == "/api/search":
            q = params.get("q", "").strip()[:200]
            if not q:
                return self._send(400, {"error": "Missing q"})
            cat = params.get("cat", "")
            ftype = params.get("type", "")
            k = int(params.get("k", "10"))
            return self._send(200, ENGINE.search(q, cat, ftype, k))
        elif url.path == "/api/doc":
            try:
                doc_id = int(params.get("id", "0"))
            except ValueError:
                return self._send(400, {"error": "Invalid id"})
            result = ENGINE.document(doc_id)
            if result is None:
                return self._send(404, {"error": "Not found"})
            return self._send(200, result)
        elif url.path == "/api/stats":
            return self._send(200, ENGINE.stats())
        else:
            self._send(404, {"error": "Not found"})

    def log_message(self, fmt, *args):
        """Suppress default logging; replace with minimal output."""
        print(f"  {self.address_string()} {fmt % args}")


def main():
    """Placeholder — startup, implemented in Task 7.5."""
    global ENGINE
    print("Initialising BrowseEngine…")
    ENGINE = BrowseEngine()
    print(f"BrowseServer ready → http://localhost:{PORT}/")
    with ThreadingHTTPServer(("", PORT), Handler) as server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


if __name__ == "__main__":
    main()
