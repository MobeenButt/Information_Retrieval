"""Standalone Week 6 Extended Boolean search app over the real FYP datasets."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import sys
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
FYP_DIR = REPO / "WEEK6_FYP"
DATA_DIR = REPO / "FYP_Data"
sys.path.insert(0, str(FYP_DIR))

from extended_boolean import QuerySyntaxError, rank_documents  # noqa: E402

HOST = "127.0.0.1"
PORT = int(os.environ.get("IR_PORT", "8080"))
DOCUMENTS: list[dict] = []
SOURCE_COUNTS: dict[str, int] = {}
SKIPPED_RECORDS: dict[str, int] = {}


def _document(doc_id: str, title: str, text: str, doc_type: str, path: Path) -> dict:
    """Create a consistently shaped, source-traceable searchable document."""
    return {
        "id": doc_id,
        "title": str(title or doc_id)[:300],
        "text": str(text or ""),
        "type": doc_type,
        "source": path.relative_to(REPO).as_posix(),
        "source_file": path.name,
    }


def _json_text(value) -> str:
    """Turn nested dataset values into readable searchable text."""
    if isinstance(value, dict):
        return " ".join(f"{key}: {_json_text(item)}" for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return " ".join(_json_text(item) for item in value)
    return str(value) if value is not None else ""


def _load_jsonl(path: Path, kind: str):
    """Yield one document per valid JSONL row, skipping malformed lines."""
    accepted = skipped = 0
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError("expected a JSON object")
            except (json.JSONDecodeError, ValueError):
                skipped += 1
                continue
            title = row.get("title") or row.get("question") or row.get("slug") or row.get("Incident_ID") or f"{kind} record {line_number}"
            accepted += 1
            yield _document(f"{kind}:{line_number}", title, _json_text(row), kind, path)
    relative = path.relative_to(REPO).as_posix()
    SOURCE_COUNTS[relative] = accepted
    SKIPPED_RECORDS[relative] = skipped


def _load_incidents(path: Path):
    """Read the incident dataset and produce one document per incident."""
    try:
        rows = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        SKIPPED_RECORDS[path.relative_to(REPO).as_posix()] = 1
        return
    if not isinstance(rows, list):
        SKIPPED_RECORDS[path.relative_to(REPO).as_posix()] = 1
        return
    accepted = 0
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            continue
        accepted += 1
        title = row.get("Summary") or row.get("Incident_ID") or f"Incident {index}"
        yield _document(f"incident:{row.get('Incident_ID', index)}", title, _json_text(row), "incident", path)
    SOURCE_COUNTS[path.relative_to(REPO).as_posix()] = accepted


def _load_log_csv(path: Path):
    """Stream structured log CSV rows as documents, skipping malformed rows."""
    accepted = skipped = 0
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as stream:
            reader = csv.DictReader(stream)
            for row_number, row in enumerate(reader, 1):
                if not row or None in row:
                    skipped += 1
                    continue
                text = " ".join(f"{key}: {value}" for key, value in row.items() if value)
                identifier = row.get("LineId") or row_number
                accepted += 1
                yield _document(f"loghub:{path.stem}:{identifier}", f"{path.parent.name} log {identifier}", text, "log", path)
    except (OSError, csv.Error):
        skipped += 1
    relative = path.relative_to(REPO).as_posix()
    SOURCE_COUNTS[relative] = accepted
    SKIPPED_RECORDS[relative] = skipped


def _load_code(path: Path):
    """Read an individual QuixBugs Python or Java source artifact."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        SKIPPED_RECORDS[path.relative_to(REPO).as_posix()] = 1
        return None
    SOURCE_COUNTS[path.relative_to(REPO).as_posix()] = 1
    return _document(f"quixbugs:{path.relative_to(DATA_DIR / '07_QuixBugs').as_posix()}", path.name, text, "code", path)


def _load_pdf(path: Path):
    """Index a PDF immediately using traceable file metadata.

    Full PDF extraction is intentionally deferred: a large research PDF must
    not block the HTTP server from starting. The file remains searchable by
    its title, filename, and source path.
    """
    text = f"Research document: {path.stem.replace('_', ' ')}. Source file: {path.name}."
    SOURCE_COUNTS[path.relative_to(REPO).as_posix()] = 1
    return _document(f"paper:{path.stem}", path.stem.replace("_", " "), text, "paper", path)


def _load_archive_bugs(path: Path):
    """Index BugsInPy descriptors and patches while retaining the archive path."""
    accepted = skipped = 0
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            for info_name in sorted(name for name in names if name.endswith("/bug.info")):
                values = {}
                for line in archive.read(info_name).decode(errors="replace").splitlines():
                    if "=" in line:
                        key, value = line.split("=", 1)
                        values[key] = value.strip().strip('"')
                patch_name = f"{info_name.rsplit('/', 1)[0]}/bug_patch.txt"
                patch = archive.read(patch_name).decode(errors="replace") if patch_name in names else ""
                text = _json_text(values) + "\n" + patch
                relative = path.relative_to(REPO).as_posix()
                documents = _document(f"bugsinpy:{info_name}", info_name.rsplit("/", 2)[-2], text, "bug", path)
                documents["source_file"] = info_name
                accepted += 1
                yield documents
    except (OSError, zipfile.BadZipFile):
        skipped += 1
    relative = path.relative_to(REPO).as_posix()
    SOURCE_COUNTS[relative] = accepted
    SKIPPED_RECORDS[relative] = skipped


def load_documents() -> list[dict]:
    """Stream the available real FYP files and return all searchable documents.

    Loaded inputs are explicitly selected from the repository-level FYP_Data
    folder: DebugBench JSONL, cloud incident JSON, structured LogHub CSV,
    QuixBugs .py/.java files, and root-level research PDFs. The data is never
    copied into Week 6. JSONL and CSV records are consumed incrementally.
    """
    SOURCE_COUNTS.clear()
    SKIPPED_RECORDS.clear()
    documents = []
    swebench_path = DATA_DIR / "01_SWE_Bench" / "swebench_lite.jsonl"
    if swebench_path.is_file():
        documents.extend(_load_jsonl(swebench_path, "swebench"))
    jsonl_path = DATA_DIR / "06_DebugBench" / "debugbench.jsonl"
    if jsonl_path.is_file():
        documents.extend(_load_jsonl(jsonl_path, "debugbench"))
    incident_path = DATA_DIR / "04_Incident_Action_Dataset" / "PAG-Synthetic-Cloud-Incident-Dataset (2).json"
    if incident_path.is_file():
        documents.extend(_load_incidents(incident_path))
    bugs_path = DATA_DIR / "02_BugsInPy" / "BugsInPy-master.zip"
    if bugs_path.is_file():
        documents.extend(_load_archive_bugs(bugs_path))
    for path in sorted((DATA_DIR / "05_Loghub").glob("*/*_2k.log_structured.csv")):
        documents.extend(_load_log_csv(path))
    quix_root = DATA_DIR / "07_QuixBugs"
    for path in sorted(quix_root.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".py", ".java"}:
            record = _load_code(path)
            if record:
                documents.append(record)
    for path in sorted(DATA_DIR.glob("*.pdf")):
        record = _load_pdf(path)
        if record:
            documents.append(record)
    return documents


def _send(handler: BaseHTTPRequestHandler, status: int, body, content_type="application/json; charset=utf-8"):
    """Write one UTF-8 HTTP response."""
    payload = body.encode("utf-8") if isinstance(body, str) else json.dumps(body, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


class Handler(BaseHTTPRequestHandler):
    """Serve the Week 6 dashboard, dataset summary, and ranked search API."""
    def do_GET(self):
        parsed = urlparse(self.path)
        params = {key: values[0] for key, values in parse_qs(parsed.query).items()}
        if parsed.path in {"/", "/fyp"}:
            try:
                _send(self, 200, (FYP_DIR / "dashboard.html").read_text(encoding="utf-8"), "text/html; charset=utf-8")
            except OSError as exc:
                _send(self, 500, {"error": str(exc)})
            return
        if parsed.path in {"/api/fyp-data", "/api/fyp-meta"}:
            _send(self, 200, {"document_count": len(DOCUMENTS), "source_counts": SOURCE_COUNTS,
                              "skipped_records": SKIPPED_RECORDS,
                              "source_root": DATA_DIR.relative_to(REPO).as_posix()})
            return
        if parsed.path == "/api/fyp-search":
            query = params.get("q", "").strip()[:500]
            if not query:
                _send(self, 400, {"error": "Enter a query."})
                return
            try:
                top_k = max(1, min(int(params.get("k", "20")), 100))
                p = float(params.get("p", "2"))
                explain = params.get("explain", "0").lower() in {"1", "true", "yes"}
                extended = params.get("extended", "1").lower() not in {"0", "false", "no"}
                must = [item.strip() for item in params.get("must", "").split(",") if item.strip()]
                must_not = [item.strip() for item in params.get("must_not", "").split(",") if item.strip()]
                file_type = params.get("file_type", "").strip().lower()
                source = params.get("source", "").strip().casefold()
                min_score = max(0.0, min(float(params.get("min_score", "0")), 1.0))
                include_ids = {item.strip() for item in params.get("include_ids", "").split(",") if item.strip()}
                exclude_ids = {item.strip() for item in params.get("exclude_ids", "").split(",") if item.strip()}
                filtered_docs = [doc for doc in DOCUMENTS
                                 if (not file_type or Path(doc["source_file"]).suffix.lower().lstrip(".") == file_type)
                                 and (not source or source in doc["source"].casefold())
                                 and (not include_ids or str(doc["id"]) in include_ids)
                                 and str(doc["id"]) not in exclude_ids]
                if extended:
                    boolean_query = query
                    if must:
                        boolean_query = f"({boolean_query}) AND ({' AND '.join(must)})"
                    if must_not:
                        boolean_query = f"({boolean_query}) AND NOT ({' OR '.join(must_not)})"
                    results = rank_documents(boolean_query, filtered_docs, p=p, top_k=top_k,
                                             explain=explain, rerank=True)
                else:
                    needle = query.casefold()
                    hits = (doc for doc in filtered_docs if needle in (doc["title"] + " " + doc["text"]).casefold())
                    results = [{"document": doc, "id": doc["id"], "score": 0.0} for doc in list(hits)[:top_k]]
                results = [result for result in results if result["score"] >= min_score]
                _send(self, 200, {"query": query, "p": p, "extended": extended,
                                  "document_count": len(DOCUMENTS), "filtered_count": len(filtered_docs),
                                  "results": results})
            except (QuerySyntaxError, ValueError) as exc:
                _send(self, 400, {"error": str(exc)})
            return
        _send(self, 404, {"error": "Not found"})

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}")


def main():
    """Load the raw dataset once, then serve the standalone Week 6 app."""
    global DOCUMENTS
    print(f"Loading raw FYP records from {DATA_DIR}")
    DOCUMENTS = load_documents()
    print(f"Loaded {len(DOCUMENTS):,} documents from {len(SOURCE_COUNTS)} source files; skipped {sum(SKIPPED_RECORDS.values())} records/files.")
    server = None
    last_error = None
    for port in [PORT] + [candidate for candidate in range(PORT + 1, PORT + 11)]:
        try:
            server = ThreadingHTTPServer((HOST, port), Handler)
            break
        except OSError as exc:
            last_error = exc
    if server is None:
        raise OSError(f"Could not bind ports {PORT}-{PORT + 10}: {last_error}")
    print(f"Week 6 ready at http://{HOST}:{server.server_port}/fyp")
    with server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Week 6 server stopped.")


if __name__ == "__main__":
    main()
