"""FYP mock data loader.

Reads the BEIR-format corpus (corpus.jsonl), queries (queries.jsonl) and
relevance judgments (qrels.tsv) from fyp_mock_data/mock_data/ir/ and
builds an InvertedIndex ready for every IR model to run against.

BEIR format
-----------
corpus.jsonl  : {"_id": "...", "title": "...", "text": "...", "metadata": {...}}
queries.jsonl : {"_id": "...", "text": "..."}
qrels.tsv     : query-id  corpus-id  score   (tab-separated, header line)
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from typing import Dict, List, Set, Tuple

from indexing import InvertedIndex

# ── paths ──────────────────────────────────────────────────────
_HERE       = os.path.dirname(os.path.abspath(__file__))
_MOCK_ROOT  = os.path.normpath(
    os.path.join(_HERE, "..", "..", "fyp_mock_data", "mock_data", "ir")
)

CORPUS_PATH  = os.path.join(_MOCK_ROOT, "corpus.jsonl")
QUERIES_PATH = os.path.join(_MOCK_ROOT, "queries.jsonl")
QRELS_PATH   = os.path.join(_MOCK_ROOT, "qrels.tsv")
INDEX_CACHE  = os.path.join(_HERE, "..", "index", "fyp_index.json")


# ── loaders ────────────────────────────────────────────────────
def load_corpus() -> List[Dict]:
    """Return list of corpus documents, each with _id, title, text, metadata."""
    docs = []
    with open(CORPUS_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                docs.append(json.loads(line))
    return docs


def load_queries() -> List[Dict]:
    """Return list of queries, each with _id and text."""
    queries = []
    with open(QUERIES_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                queries.append(json.loads(line))
    return queries


def load_qrels() -> Dict[str, Dict[str, int]]:
    """Return {query_id: {corpus_id: relevance_score}} from qrels.tsv.

    Relevance scores: 2 = highly relevant, 1 = relevant, 0 = not relevant.
    """
    qrels: Dict[str, Dict[str, int]] = defaultdict(dict)
    with open(QRELS_PATH, encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line or i == 0:          # skip header
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                qid, cid, score = parts[0], parts[1], int(parts[2])
                qrels[qid][cid] = score
    return dict(qrels)


# ── index builder ──────────────────────────────────────────────
def build_fyp_index(force: bool = False) -> Tuple[InvertedIndex, Dict[str, str]]:
    """Build (or reload) an InvertedIndex from the FYP corpus.

    Returns
    -------
    idx          InvertedIndex over the FYP corpus
    id_map       {sequential_int_id -> original_corpus_id}  (needed for metrics)
    """
    id_map_path = INDEX_CACHE.replace(".json", "_idmap.json")

    # try loading cached index
    if not force and os.path.exists(INDEX_CACHE) and os.path.exists(id_map_path):
        idx = InvertedIndex.load(INDEX_CACHE)
        with open(id_map_path, encoding="utf-8") as f:
            id_map = {int(k): v for k, v in json.load(f).items()}
        return idx, id_map

    docs  = load_corpus()
    idx   = InvertedIndex()
    id_map: Dict[int, str] = {}          # int_id -> original string id

    for seq_id, doc in enumerate(docs, start=1):
        orig_id = doc["_id"]
        id_map[seq_id] = orig_id
        # merge title + text; carry original id, type, service as metadata
        meta = doc.get("metadata", {})
        fields = {
            "title": doc.get("title", "") or "",
            "text":  doc.get("text", ""),
            "type":  meta.get("type", ""),
            "service": meta.get("service", ""),
        }
        idx.add_document(seq_id, fields)

    idx.finalize()
    os.makedirs(os.path.dirname(INDEX_CACHE), exist_ok=True)
    idx.save(INDEX_CACHE)
    with open(id_map_path, "w", encoding="utf-8") as f:
        json.dump(id_map, f)

    return idx, id_map


# ── convenience: translate ranked int ids back to corpus string ids ─────────
def translate_results(hits: List[Dict], id_map: Dict[int, str]) -> List[Dict]:
    """Replace hit['id'] (int) with the original corpus string id."""
    out = []
    for h in hits:
        h2 = dict(h)
        h2["corpus_id"] = id_map.get(h["id"], str(h["id"]))
        out.append(h2)
    return out
