# Spec Review: Browsing and Navigation Module (Week 5)

The spec covers a self-contained Python+JS browsing module layered on top of the existing IR search engine. Requirements defines 11 requirements (10 user-facing features + 1 delivery constraint). Design proposes `BrowseEngine` + `BrowseServer` + a vanilla JS SPA. Tasks breaks implementation into 16 numbered tasks with optional property-based tests. The three documents are well-aligned overall, but several technical feasibility gaps and a handful of coverage mismatches need resolution before implementation begins.

**Watch for:**
- `SearchEngine.search()` returns a `"hits"` key inside a dict — the design's `BrowseEngine.search()` assumes this shape but mutates `raw["total"]` to `len(hits)` after filtering, which discards the actual collection-level total the frontend may need. (confirmed)
- The `documents.json` primary corpus has integer `id` fields, but `InvertedIndex` assigns its own sequential integer IDs when indexing `data/`. These two ID spaces collide — a document from `documents.json` with `id=3` is not the same as index doc ID 3 from the supporting corpus. `BrowseEngine.search()` does `self._docs_by_id.get(hit["id"])` assuming the index IDs match the JSON IDs. They won't. (confirmed)
- Req 6.5 (derived metadata display for date/author/language) has no implementation in design or tasks. (confirmed)
- The design places `browse_index.json` under `search-engine/index/`, violating the self-contained Week 5 containment required by Req 11.1. (confirmed)

**Verdict**: NEEDS_CHANGES

---

## High-level view

The three layers of the spec — requirements, design, tasks — tell a consistent story about a BM25-backed browse module with a six-category tree, back/forward history, and a black/yellow SPA. The architecture is coherent and the task dependency graph correctly orders waves. The fatal gap is the ID space collision: `documents.json` carries its own `id` field (1–25), and `InvertedIndex` assigns independent sequential IDs when it scans the `data/` folder. The design's `BrowseEngine.search()` looks up `self._docs_by_id[hit["id"]]` assuming these two numbering schemes agree, but they don't unless the JSON documents are what the indexer processes. The corpus loading strategy needs to be clarified — either index `documents.json` directly (treating each paper's text fields as the document body) or reconcile the two ID namespaces explicitly.

The `file_type` story is a related design gap. The primary corpus (`documents.json`) has no `file_type` field, so the design defaults every paper to `"txt"`. The supporting corpus (`data/` folder) has txt/json/csv/xml files but represents a different document set. Req 6.3 (file-type filter) and Req 11.4 (load supporting corpus) imply the filter should work across both, but the design only applies `file_type` post-filtering against `self._docs_by_id` which is keyed on primary-corpus docs. Supporting-corpus-only documents would never appear in browse results.

Requirement 6.5 — derived metadata (date/author/language) displayed as marked filter elements — appears in requirements, is absent from design, and has no task. This is a confirmed coverage gap; the glossary even defines "Derived Metadata" but no design section implements it.

The index containment issue is minor but real: `browse_index.json` is written to `search-engine/index/`, which lives outside `Week 5/`. Req 11.1 requires the module to "reside entirely within the Week 5 folder." A simple fix is redirecting the index path to `Week 5/index/`.

The `BrowseEngine.related_docs()` design calls `self._engine.search(query, model="bm25", k=len(self._docs))` — for a 25-document corpus this is k=25, which is fine — but `SearchEngine.search()` only looks up `idx.docs`, which holds the supporting corpus, not the primary corpus papers. If the corpora aren't reconciled, related-doc computation will return zero hits for any query derived from `documents.json` titles and abstracts.

---

<details>
<summary>Issues (9)</summary>

1. **ID space collision** — `documents.json` `id` values (1–25) and `InvertedIndex` sequential IDs (assigned by file sort order over `data/`) are independent namespaces. `BrowseEngine.search()` does `self._docs_by_id.get(hit["id"])` which will silently miss or mismap documents. Either index `documents.json` directly (build a fresh `InvertedIndex` from the paper text fields) or define an explicit ID-reconciliation step.

2. **`search()` `total` field shadowing** — `BrowseEngine.search()` overwrites `raw["total"]` with `len(hits)` (post-filter count). `SearchEngine.search()` puts the pre-filter collection total in `"total"`. If the frontend uses `total` for pagination or display, it will see the filtered count, not the collection count. Either rename the filtered count or document the intended semantics.

3. **Req 6.5 not designed or tasked** — Derived metadata display (date/author/language as marked filter chips) is in Req 6.5 and the glossary but has no design section and no task. Either implement it or explicitly descope it in the spec.

4. **`browse_index.json` outside Week 5/** — The design writes the index to `../search-engine/index/browse_index.json`, violating Req 11.1 ("reside entirely within the Week 5 folder"). Move the index path to `Week 5/index/browse_index.json`.

5. **`related_docs()` queries an index that doesn't contain primary corpus text** — If `load_or_build(DATA_DIR, INDEX_PATH)` indexes `data/` files (supporting corpus), BM25 queries built from `documents.json` titles and abstracts will find few or no matches because the paper content was never indexed. Task 5.1 needs to explicitly specify which corpus the BM25 call is made against.

6. **`/api/search` empty-query handling inconsistency** — The design's `do_GET()` code snippet passes the raw (possibly empty) `q` to `ENGINE.search()` without the 400 check. Task 7.3 lists the 400 guard as a routing responsibility, but the design pseudocode omits it. The spec should be consistent on where the guard lives.

7. **`document()` method contract gap** — Design Sec 2g says the `/api/doc` response includes `methodology` and `results`. The design also correctly notes these come from `self._docs`, not from `self._engine.document()`. Task 6 implements `BrowseEngine.document()` and correctly reads `self._docs_by_id`. However, the design's `app.py` snippet passes the raw return of `ENGINE.document()` directly to `_send()` with no null-check — the null/404 branch is described in the error table but absent from the code snippet. The code snippet should match the described behavior.

8. **Keyword filter (Req 6.4) treated as search, not pure filter** — The design routes keyword filter through `/api/search` as the `q` parameter. This means keyword filtering changes the result ranking, not just membership. Req 6.4 says "display only documents whose content contains the keyword," implying a membership filter, not a re-rank. The design's choice is defensible but should be explicitly acknowledged so the task author doesn't implement a separate content-scan filter.

9. **`search()` over-fetch ceiling for small corpora** — `BrowseEngine.search()` over-fetches with `k=50` from a 25-document corpus, which is harmless but means `k=50` always fetches the entire corpus. The design note says "keeps response times low for the 25-document corpus" — this is correct, but the k=50 constant should be documented as corpus-size-aware, otherwise a future corpus expansion silently degrades filter recall.

</details>

---

<details>
<summary>Details</summary>

### ID namespace collision between documents.json and InvertedIndex

The design's `BrowseEngine.__init__` calls `load_or_build(DATA_DIR, INDEX_PATH)` where `DATA_DIR` is `search-engine/data/`. `InvertedIndex.build_index()` assigns IDs by iterating `sorted(os.listdir(folder))` — so `01_information_retrieval_basics.txt` gets `doc_id=1`, `02_inverted_index.txt` gets `doc_id=2`, and so on through `documents.json` itself (which would be included as a JSON file in the data directory, or excluded — the design doesn't say).

`documents.json` contains 25 papers, each with an `id` field (confirmed integer). When `BrowseEngine.search()` gets back a hit from `self._engine.search()`, it does:

```python
doc = self._docs_by_id.get(hit["id"])
```

For this to work, the hit's `id` must match a key in `self._docs_by_id`. But `self._docs_by_id` is keyed on `documents.json`'s own `id` values, while `hit["id"]` is the `InvertedIndex`'s sequential doc_id from sorting `data/`. These will coincide only by accident for the first 25 files.

The correct fix is to build the `InvertedIndex` from `documents.json` content directly, assigning each paper's `id` as the `doc_id`. This ensures `hit["id"]` maps back to the same paper in `self._docs_by_id`. Task 2.1 says "Load `documents.json` into `self._docs`" and "Call `load_or_build` using the existing `InvertedIndex`" but does not specify whether `load_or_build` operates over `data/` (supporting corpus) or over derived content from `documents.json`. This ambiguity must be resolved.

### file_type filter coverage gap

`documents.json` has no `file_type` field. The design defaults all primary corpus documents to `file_type="txt"`. The supporting corpus files in `data/` have genuine mixed types (txt/json/csv/xml). But the supporting corpus files are distinct documents with their own content — they are not the 25 research papers in `documents.json`.

The consequence: filtering by `file_type=json` would match zero primary corpus papers (all default to "txt") and would only match supporting corpus files — but those files are not in `self._docs_by_id`, so they're filtered out in `BrowseEngine.search()`. The filter silently returns no results for any type other than "txt".

Req 6.3 and the supporting corpus note in Req 11.4 need to be reconciled with this reality. Either the spec should acknowledge that file_type filtering applies only to the supporting corpus (and browsing is primary-corpus-only), or the design needs an explicit strategy for exposing supporting corpus documents through the browse interface.

### Req 6.5: Derived metadata is specced but absent from design and tasks

Req 6.5: "WHERE a metadata field for date, author, or language is missing from the source data, THE Frontend SHALL display that field as a UI filter element populated with Derived Metadata and SHALL mark the value as derived."

The glossary defines "Derived Metadata" explicitly. No design section describes how date, author, or language are derived from document content. No task implements this. The filter bar in the design (Sec 3, Filter Bar) only shows Category, File Type, and Keyword controls — no date, author, or language.

This is either an intentional descope (in which case Req 6.5 should be marked as out of scope) or a genuine gap. Given that `documents.json` has no date/author/language fields, implementing this would require heuristic extraction from `abstract`, `methodology`, or `results` text — non-trivial and not described anywhere.

### Index path containment violation

```python
INDEX_PATH = os.path.join(
    os.path.dirname(__file__), "..", "search-engine", "index", "browse_index.json"
)
```

This writes `browse_index.json` to `search-engine/index/`, which is outside `Week 5/`. Req 11.1 requires the BrowseModule to "reside entirely within the Week 5 folder as a self-contained deliverable." The fix is trivial:

```python
INDEX_PATH = os.path.join(os.path.dirname(__file__), "index", "browse_index.json")
```

Task 2.1 explicitly says "build or reuse `browse_index.json` under `search-engine/index/`", so the task also encodes the violation. Both must be corrected.

### related_docs() and BM25 over the wrong corpus

`related_docs()` builds a query from `source["title"] + " " + source["abstract"]` and calls `self._engine.search(query, model="bm25", k=len(self._docs))`. `self._engine` wraps the index built from `load_or_build(DATA_DIR, ...)` over the `data/` folder. The supporting corpus `.txt` files contain IR course notes, not research paper abstracts. BM25 queries derived from paper titles and abstracts will find partial matches in course notes (since the topics overlap), but the hit IDs will be supporting-corpus IDs, not primary-corpus IDs, so the `self._docs_by_id.get(hit["id"])` lookup will return `None` for most hits. Related documents will be systematically under-computed.

The design's intent — finding similar papers using BM25 — only works if the index contains the paper content. Task 5.1 must specify building (or augmenting) the index from `documents.json` text fields.

### /api/search empty-query guard placement

```python
elif url.path == "/api/search":
    q = params.get("q", "").strip()[:200]
    ...
    return self._send(200, ENGINE.search(q, cat, ftype, k))
```

No 400 check here. The error table says "Empty query to `/api/search` → Returns `{"error": "Missing q"}` HTTP 400." Task 7.3 says "validate `q` non-empty (400) then `ENGINE.search()`." The pseudocode in the design contradicts both. A reader implementing from the design pseudocode will skip the guard; the task description has it right. The design's code snippet should add the check:

```python
if not q:
    return self._send(400, {"error": "Missing q"})
```

### Feature coverage matrix

| Req | In Requirements | In Design | In Tasks | Notes |
|-----|----------------|-----------|----------|-------|
| 1 Category Menu | ✓ | ✓ | ✓ (2.3, 12.1) | |
| 2 Mode Toggle | ✓ | ✓ | ✓ (12.3) | |
| 3 Breadcrumb | ✓ | ✓ | ✓ (12.2) | |
| 4 Related Docs | ✓ | ✓ | ✓ (5.1, 13.2) | ID collision risk |
| 5 Recently Viewed | ✓ | ✓ | ✓ (11.3) | |
| 6 Filters | ✓ | ✓ (partial) | ✓ (12.3, 3.4) | Req 6.5 not designed |
| 7 Nav History | ✓ | ✓ | ✓ (11.1, 14) | |
| 8 Document Preview | ✓ | ✓ | ✓ (13.1) | |
| 9 Internal Links | ✓ | ✓ | ✓ (5.5, 13.2) | |
| 10 UI/Accessibility | ✓ | ✓ | ✓ (9, 14) | |
| 11 Standalone Delivery | ✓ | ✓ (partial) | ✓ (1, 15) | Index path outside Week 5/ |

### Design elements with no requirement backing

`Engine.stats()` returns `{"doc_count", "categories", "indexed"}`. No requirement explicitly mandates a `/api/stats` endpoint — its existence is implied only by the startup loading spinner note in the error handling table ("Loading spinner shown until `/api/stats` responds"). This is an undocumented assumption in requirements; if the spinner behavior is required, add a criterion in Req 10 or Req 11.

### Task dependency wave ordering issue

Wave 4 includes task 5.1 (`related_docs`) as a parallel peer of property tests 3.5–3.8. But 5.1 depends on `BrowseEngine.search()` (task 3.4, wave 3) being complete — this is satisfied. However, tasks 5.2–5.4 (property tests for related docs) are in wave 5 and depend on 5.1, which is correct. The only oddity is that task 6 (`document()` implementation) is not in any wave — it's listed as a standalone task between waves. This could cause a wave executor to skip it or run it in parallel with unrelated tasks. Task 6 should be explicitly placed in a wave after wave 6 (after 5.5–5.7) and before wave 7 (task 7.1).

</details>

---

<details>
<summary>File map</summary>

| File | What was reviewed |
|------|------------------|
| `.kiro/specs/browsing-navigation-module/requirements.md` | All 11 requirements, glossary, EARS-patterned acceptance criteria |
| `.kiro/specs/browsing-navigation-module/design.md` | Architecture, BrowseEngine interfaces, data models, error handling table, correctness properties, testing strategy |
| `.kiro/specs/browsing-navigation-module/tasks.md` | 16 implementation tasks, 15 property tests, dependency graph |
| `search-engine/backend/engine.py` | `SearchEngine.search()` return shape, `make_snippet()`, `SearchEngine.document()` |
| `search-engine/backend/indexer.py` | `InvertedIndex`, `load_or_build()`, `build_index()`, `read_documents()`, ID assignment logic |

</details>
