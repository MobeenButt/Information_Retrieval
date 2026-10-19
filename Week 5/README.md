# Week 5 — Browsing and Navigation Module

A self-contained browsing and navigation layer on top of the existing
`search-engine` backend. It exposes a JSON API via a Python `http.server`
and serves a single-page HTML frontend.

---

## Folder Layout

```
Week 5/
├── app.py          BrowseServer — HTTP routing (BaseHTTPRequestHandler)
├── browse.py       BrowseEngine — domain logic (category tree, search, related docs)
├── index.html      Single-page frontend (vanilla HTML/CSS/JS)
├── run.bat         Windows launcher
└── README.md       This file

../search-engine/
├── backend/        Imported via sys.path (read-only, never modified)
│   ├── indexer.py
│   ├── engine.py
│   ├── ranker.py
│   └── preprocess.py
├── data/
│   └── documents.json   Primary corpus (25 research papers)
└── index/          Used by the original search-engine backend; Week 5 builds
                    its own in-memory index from documents.json
```

> **Note:** Both `app.py` and `browse.py` insert `../search-engine/backend`
> into `sys.path` at startup. The original backend files are never modified.

---

## Setup

1. Ensure Python 3.10+ is installed.
2. Install optional dependencies (only `hypothesis` for property tests):
   ```
   pip install hypothesis
   ```
3. Run the server:
   ```
   python app.py
   ```
   or on Windows:
   ```
   run.bat
   ```
4. Open `http://localhost:8080/` in a browser.

---

## API Endpoints

| Endpoint | Method | Description | Example |
|---|---|---|---|
| `/` or `/index.html` | GET | Serve the frontend SPA | `GET /` |
| `/api/categories` | GET | Return the full category tree | `GET /api/categories` |
| `/api/browse` | GET | Browse docs by category/subcategory | `GET /api/browse?cat=AI&sub=NLP` |
| `/api/search` | GET | BM25 search with category, subcategory, file type, and available metadata filters | `GET /api/search?q=retrieval&cat=IR&sub=Evaluation&type=txt&k=10` |
| `/api/compare` | GET | Compare supported ranking models for one query | `GET /api/compare?q=retrieval&models=bm25,tfidf,boolean,overlap,nonoverlap,bim,proximal&k=10` |
| `/api/doc` | GET | Full document + related + internal links | `GET /api/doc?id=4` |
| `/api/stats` | GET | Server stats (doc count, categories, index status) | `GET /api/stats` |

### Example Responses

**`/api/stats`**
```json
{"doc_count": 25, "categories": ["AI", "Cybersecurity", "Healthcare", "Databases", "SoftwareEngineering", "IR"], "indexed": true}
```

**`/api/browse?cat=AI&sub=NLP`**
```json
[{"id": 2, "title": "Transformer Models for NLP", "abstract": "...", "category": "AI", "file_type": "txt", "subcategory": "NLP"}]
```

**`/api/doc?id=4`**
```json
{
  "id": 4, "title": "Reinforcement Learning for Autonomous Systems",
  "abstract": "...", "methodology": "...", "results": "...",
  "category": "AI", "subcategory": "Reinforcement Learning", "file_type": "txt",
  "related": [{"id": 1, "title": "...", "score": 0.812, "same_category": true}],
  "internal_links": [{"id": 2, "title": "Transformer Models for NLP", "hits": 3}]
}
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Alt + Left` | Navigate Back |
| `Alt + Right` | Navigate Forward |
| `Escape` | Close document preview overlay |
| `Tab` | Move focus between interactive controls |
| `Enter` / `Space` | Activate focused control |

---

## Notes

- The server uses only Python standard library (`http.server`, `json`, `urllib`).
- All CORS headers (`Access-Control-Allow-Origin: *`) are emitted on every response.
- The Week 5 search index is built from `documents.json` each time the server starts,
  keeping result IDs and titles aligned with the corpus shown in the UI. It does not
  reuse the separate search-engine corpus index.
- The comparison page runs the query through all seven supported ranking models by
  default; individual models can be deselected. Results include score details,
  available engine explanations, and a rank-movement chart.
- Date, author, and language filters use optional document metadata (`date` /
  `publication_date` / `year`, `author` / `authors`, and `language` / `lang`).
  Topic filtering checks topic/tag metadata and the existing category, subcategory,
  and title. The current `documents.json` corpus does not include date, author,
  or language fields, so those filters return no matches until metadata is added.
- If a search has no exact matches, the server retries only unambiguous one-character
  spelling corrections for terms of at least five characters. The response includes
  `corrected_query`, and the UI indicates which corrected query produced the results.
- `sys.path` injection in both `app.py` and `browse.py` points to
  `../search-engine/backend` relative to the `Week 5/` folder.
- `run.bat` starts the offline vanilla HTML/CSS/JavaScript interface and local API.
  The server tries ports 8080 through 8090 and prints the URL it successfully binds.
