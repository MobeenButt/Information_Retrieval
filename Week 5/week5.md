I’ll trace the Week 5 folder end to end: documentation, backend flow, browser UI, scripts, and tests, then explain how a request moves through the system.

Read 

Read 

Read 

Read 

Read 

Read 

Read 

I’ll trace the Week 5 implementation from the README and source files, then explain the architecture, request flow, indexing/search logic, browser UI, and tests in a connected step-by-step way.

Read 
Completed with input: {
  "path": "D:\\sem\\7 Sem\\IR\\Assignments\\Week 5\\README.md"
}

Read 
Completed with input: {
  "path": "D:\\sem\\7 Sem\\IR\\Assignments\\Week 5\\app.py"
}

Read 
Completed with input: {
  "path": "D:\\sem\\7 Sem\\IR\\Assignments\\Week 5\\browse.py"
}

Read 
Completed with input: {
  "path": "D:\\sem\\7 Sem\\IR\\Assignments\\Week 5\\index.html"
}

Read 
Completed with input: {
  "path": "D:\\sem\\7 Sem\\IR\\Assignments\\Week 5\\test_browse_smoke.py"
}

Read 
Completed with input: {
  "path": "D:\\sem\\7 Sem\\IR\\Assignments\\Week 5\\_integration_check.py"
}

Read 
Completed with input: {
  "path": "D:\\sem\\7 Sem\\IR\\Assignments\\Week 5\\run.bat"
}

The Week 5 folder is a small full-stack module: `browse.py` contains the domain engine, `app.py` exposes it over HTTP, and `index.html` is the client. I’m now mapping the engine’s data model and each frontend interaction so the explanation covers how a request travels end to end.

Search for `^(class|def) |BrowseEngine|category_tree|def browse|def search|def document|d...`

Search for `fetch\(|/api/|function |class=|id=|addEventListener|history|Alt|Escape`

Read , lines 1 to 220
Completed with input: {
  "path": "D:\\sem\\7 Sem\\IR\\Assignments\\Week 5\\browse.py",
  "view_range": [
    1,
    220
  ]
}

Read , lines 1 to 260
Completed with input: {
  "path": "D:\\sem\\7 Sem\\IR\\Assignments\\Week 5\\index.html",
  "view_range": [
    1,
    260
  ]
}

Read , lines 156 to 430
Completed with input: {
  "path": "D:\\sem\\7 Sem\\IR\\Assignments\\Week 5\\browse.py",
  "view_range": [
    156,
    430
  ]
}

Read , lines 710 to 930
Completed with input: {
  "path": "D:\\sem\\7 Sem\\IR\\Assignments\\Week 5\\index.html",
  "view_range": [
    710,
    930
  ]
}

Read , lines 930 to 1240
Completed with input: {
  "path": "D:\\sem\\7 Sem\\IR\\Assignments\\Week 5\\index.html",
  "view_range": [
    930,
    1240
  ]
}

Read , lines 1240 to 1785
Completed with input: {
  "path": "D:\\sem\\7 Sem\\IR\\Assignments\\Week 5\\index.html",
  "view_range": [
    1240,
    1785
  ]
}

Read , lines 330 to 430
Completed with input: {
  "path": "D:\\sem\\7 Sem\\IR\\Assignments\\Week 5\\browse.py",
  "view_range": [
    330,
    430
  ]
}

Read , lines 1430 to 1765
Completed with input: {
  "path": "D:\\sem\\7 Sem\\IR\\Assignments\\Week 5\\index.html",
  "view_range": [
    1430,
    1765
  ]
}

Read , lines 1670 to 1805
Completed with input: {
  "path": "D:\\sem\\7 Sem\\IR\\Assignments\\Week 5\\index.html",
  "view_range": [
    1670,
    1805
  ]
}

Read , lines 1 to 220
Completed with input: {
  "path": "D:\\sem\\7 Sem\\IR\\Assignments\\search-engine\\backend\\engine.py",
  "view_range": [
    1,
    220
  ]
}

Read , lines 1 to 240
Completed with input: {
  "path": "D:\\sem\\7 Sem\\IR\\Assignments\\search-engine\\backend\\indexer.py",
  "view_range": [
    1,
    240
  ]
}

Read , lines 1 to 200
Completed with input: {
  "path": "D:\\sem\\7 Sem\\IR\\Assignments\\search-engine\\backend\\ranker.py",
  "view_range": [
    1,
    200
  ]
}

Read , lines 1 to 60
Completed with input: {
  "path": "D:\\sem\\7 Sem\\IR\\Assignments\\search-engine\\data\\documents.json",
  "view_range": [
    1,
    60
  ]
}

# Week 5: Browsing and Navigation Module

The Week 5 folder implements a complete browsing and navigation application for an Information Retrieval corpus. It has three main layers:

1. **Backend/domain logic** — `browse.py`
2. **HTTP API/server** — `app.py`
3. **Browser frontend** — `index.html`

It reuses the existing search backend from the `search-engine/backend/` folder instead of implementing indexing and ranking again.

---

## 1. Folder structure

```text
Week 5/
├── app.py
├── browse.py
├── index.html
├── README.md
├── run.bat
├── test_browse_smoke.py
└── _integration_check.py
```

The main corpus comes from:

```text
search-engine/data/documents.json
```

The reusable IR backend contains:

```text
search-engine/backend/
├── indexer.py
├── engine.py
├── ranker.py
└── preprocess.py
```

The Week 5 code imports these files dynamically using `sys.path`.

---

# 2. Application startup

You can start the system with:

```powershell
cd "D:\sem\7 Sem\IR\Assignments\Week 5"
python app.py
```

Or on Windows:

```text
run.bat
```

The `run.bat` file simply changes the current directory to the Week 5 folder and runs:

```bat
python app.py
```

When `app.py` starts, it performs the following operations:

```python
ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(ROOT, "..", "search-engine", "backend")
sys.path.insert(0, BACKEND)
```

This allows Week 5 to import:

```python
from browse import BrowseEngine
```

The server then creates a single global engine:

```python
ENGINE = BrowseEngine()
```

Finally, it starts a multithreaded HTTP server:

```python
with ThreadingHTTPServer(("", PORT), Handler) as server:
    server.serve_forever()
```

The application runs at:

```text
http://localhost:8080/
```

---

# 3. `browse.py`: the main domain layer

`browse.py` contains the `BrowseEngine` class.

Its responsibilities are:

- Loading the corpus
- Deriving document metadata
- Building or loading the inverted index
- Creating category/subcategory data
- Browsing documents
- Searching documents with BM25
- Finding related documents
- Generating internal links
- Returning complete document information
- Returning system statistics

---

## 3.1 Loading the document corpus

The main corpus is located at:

```python
DOCUMENTS_JSON = os.path.join(
    _HERE,
    "..",
    "search-engine",
    "data",
    "documents.json"
)
```

Each document contains fields such as:

```json
{
  "id": 1,
  "title": "Deep Neural Networks for Image Classification",
  "abstract": "...",
  "methodology": "...",
  "results": "...",
  "category": "AI"
}
```

During initialization, the documents are read:

```python
with open(docs_path, encoding="utf-8") as fh:
    raw_docs = json.load(fh)
```

Each document is copied into an internal list:

```python
self._docs = []
self._docs_by_id = {}
```

`self._docs` is used for iteration, while `self._docs_by_id` provides fast lookup by document ID.

---

## 3.2 Deriving the file type

The system scans the `search-engine/data` folder and maps numeric filename prefixes to file extensions.

For example:

```text
01_information_retrieval_basics.txt
02_inverted_index.txt
26_search_algorithms.json
27_ir_evaluation_benchmarks.csv
28_query_processing.xml
```

The numeric prefix becomes the document ID:

```text
01 → document ID 1 → txt
26 → document ID 26 → json
27 → document ID 27 → csv
28 → document ID 28 → xml
```

This mapping is stored in `_ext_map`.

Then each document receives a derived `file_type`:

```python
doc["file_type"] = _ext_map.get(doc_id, "txt")
```

If no matching source file is found, the system defaults to:

```text
txt
```

This value is later used by the file-type filter in the UI.

---

## 3.3 Deriving subcategories

The application has six main categories:

```python
AI
Cybersecurity
Healthcare
Databases
SoftwareEngineering
IR
```

Each category has a keyword map. For example:

```python
"AI": {
    "NLP": ["natural language", "transformer", "sentiment", "text"],
    "Computer Vision": ["image", "convolutional", "vision", "visual", "radiograph"],
    "Reinforcement Learning": ["reinforcement", "autonomous", "agent", "policy"],
    "Generative Models": ["generative", "adversarial", "gan", "synthesize"]
}
```

The function `_derive_subcategory()` checks the document title against these keywords.

For example:

```text
Title:
Transformer Models for Natural Language Processing
```

Matches:

```text
AI → NLP
```

Another example:

```text
Reinforcement Learning for Autonomous Systems
```

Matches:

```text
AI → Reinforcement Learning
```

The first matching subcategory is selected:

```python
for subcat, keywords in SUBCAT_KEYWORDS.get(category, {}).items():
    if any(kw in lower for kw in keywords):
        return subcat
```

If no keyword matches, the document is placed into:

```text
_unclassified
```

The frontend displays `_unclassified` as:

```text
Other
```

---

## 3.4 Reusing the inverted index

The Week 5 implementation does not create a new search index manually. It reuses the existing backend indexer:

```python
from indexer import InvertedIndex, load_or_build
```

The index is loaded or generated here:

```python
self._index = load_or_build(
    os.path.normpath(DATA_DIR),
    index_path
)
```

The persistent index is stored at:

```text
search-engine/index/browse_index.json
```

The reused `indexer.py` performs the following:

1. Reads files based on extension.
2. Extracts titles and text.
3. Applies text preprocessing.
4. Tokenizes and stems terms.
5. Builds a term-to-document posting list.
6. Stores term frequencies.
7. Calculates document lengths.
8. Calculates average document length.
9. Saves the index to JSON.

The index structure is conceptually:

```text
term → {
    document_id: term_frequency
}
```

For example:

```text
neural → {
    1: 4,
    3: 3,
    5: 2
}
```

The title is given extra importance in the indexer:

```python
terms = preprocess(title) * TITLE_BOOST + preprocess(text)
```

`TITLE_BOOST` is equal to `2`, so title terms count twice.

---

## 3.5 Creating the search engine

After loading the index, `BrowseEngine` creates a reusable `SearchEngine`:

```python
self._engine = SearchEngine(self._index)
```

The `engine.py` handles:

- Query preprocessing
- Stop-word removal
- Stemming
- Posting-list lookup
- Ranking
- Snippet generation
- Returning search metadata

Week 5 specifically uses the BM25 ranking model.

---

# 4. Category browsing

## 4.1 `category_tree()`

The `category_tree()` method generates the complete category hierarchy.

Its output has this general structure:

```json
{
  "AI": {
    "doc_count": 5,
    "subcategories": {
      "Computer Vision": {
        "doc_count": 2,
        "docs": [
          {
            "id": 1,
            "title": "Deep Neural Networks for Image Classification",
            "abstract": "...",
            "category": "AI",
            "file_type": "txt",
            "subcategory": "Computer Vision"
          }
        ]
      }
    }
  }
}
```

All known categories are initialized first, even if they contain no documents:

```python
for cat in SUBCAT_KEYWORDS:
    tree[cat] = {
        "doc_count": 0,
        "subcategories": {}
    }
```

Then each document is inserted into:

1. Its main category
2. Its derived subcategory

The helper `_strip_doc()` removes unnecessary fields and returns a lightweight document object for list responses.

This avoids sending the complete methodology and results fields when only a summary is required.

---

## 4.2 `browse(cat, sub)`

The `browse()` method returns documents according to optional filters:

```python
browse(cat="", sub="")
```

Possible cases:

### Browse everything

```text
/api/browse
```

Returns all documents.

### Browse a category

```text
/api/browse?cat=AI
```

Returns only documents where:

```python
doc["category"] == "AI"
```

### Browse a subcategory

```text
/api/browse?cat=AI&sub=NLP
```

Returns only documents whose derived subcategory is `NLP`.

### Browse unclassified documents

```text
/api/browse?cat=AI&sub=_unclassified
```

Returns documents that did not match any subcategory keyword.

The method returns lightweight documents using `_strip_doc()`.

---

# 5. Search implementation

## 5.1 BM25 search

The `search()` method is:

```python
search(query, cat="", file_type="", k=10)
```

It calls the existing search engine:

```python
raw = self._engine.search(
    query,
    model="bm25",
    k=50
)
```

The engine preprocesses the query and ranks documents using BM25.

BM25 considers:

- How often query terms occur in a document
- How rare the terms are across the collection
- The document length
- Average document length

The BM25 implementation is located in `ranker.py`.

The general BM25 score is based on:

```text
term frequency
inverse document frequency
document length normalization
```

---

## 5.2 Why the engine retrieves 50 results first

The Week 5 code requests up to 50 raw results:

```python
raw = self._engine.search(query, model="bm25", k=50)
```

It does this because category and file-type filtering are applied afterward.

For example, if the user requests:

```text
q = neural
cat = AI
type = txt
k = 10
```

The code:

1. Gets the top 50 BM25 results.
2. Removes results that are not in the `AI` category.
3. Removes results that are not `txt`.
4. Stops after collecting 10 valid results.

This avoids returning fewer results simply because filtering was performed after ranking.

---

## 5.3 Search result metadata

The original search engine returns fields such as:

```json
{
  "id": 1,
  "title": "...",
  "score": 3.42,
  "snippet": "...",
  "matched": ["neural", "network"]
}
```

The Week 5 layer adds:

```json
{
  "category": "AI",
  "file_type": "txt"
}
```

The final response has this shape:

```json
{
  "query": "neural network",
  "hits": [
    {
      "id": 1,
      "title": "Deep Neural Networks for Image Classification",
      "score": 3.42,
      "snippet": "...",
      "matched": ["neural", "network"],
      "category": "AI",
      "file_type": "txt"
    }
  ],
  "total": 1,
  "model": "bm25"
}
```

The results remain sorted in descending score order.

---

# 6. Related document discovery

The `related_docs()` method finds documents related to a selected document.

```python
related_docs(doc_id, n=5)
```

The source document's title and abstract are combined into a query:

```python
query = source["title"] + " " + source["abstract"]
```

That combined text is searched using BM25:

```python
raw = self._engine.search(
    query,
    model="bm25",
    k=len(self._docs)
)
```

The source document itself is removed from the results.

Then a category boost is applied:

```python
SAME_CAT_BOOST = 1.5
```

If a candidate belongs to the same category as the source document:

```python
score = hit["score"] * 1.5
```

Otherwise:

```python
score = hit["score"]
```

Each result receives:

```json
{
  "id": 3,
  "title": "Convolutional Neural Networks for Medical Image Analysis",
  "score": 4.21,
  "same_category": true
}
```

The final list is sorted again after boosting and truncated to five documents.

---

# 7. Internal links

The `internal_links()` method creates link suggestions between documents.

```python
internal_links(doc_id)
```

It builds a candidate set containing:

1. Documents in the same category
2. Documents returned by `related_docs()`

The source document is excluded.

The source document's full text is combined:

```python
title
abstract
methodology
results
```

For each candidate, the candidate title is split into words.

Words are ignored if:

- They are shorter than three characters
- They are stop words

For example, words such as:

```text
the
for
of
a
```

are ignored.

The remaining title words are searched in the source document's full text.

The number of matching words becomes the `hits` count:

```json
{
  "id": 2,
  "title": "Transformer Models for Natural Language Processing",
  "hits": 3
}
```

The links are sorted by hit count and limited to:

```python
MAX_LINKS = 5
```

This produces meaningful internal navigation suggestions rather than just random documents.

---

# 8. Full document endpoint

The `document()` method returns the complete document:

```python
document(doc_id)
```

The response includes:

```json
{
  "id": 1,
  "title": "...",
  "abstract": "...",
  "methodology": "...",
  "results": "...",
  "category": "AI",
  "subcategory": "Computer Vision",
  "file_type": "txt",
  "related": [],
  "internal_links": []
}
```

The related documents and internal links are calculated when the document is requested.

If the document does not exist, the method returns:

```python
None
```

The HTTP layer converts that into:

```json
{
  "error": "Not found"
}
```

with HTTP status `404`.

---

# 9. `app.py`: HTTP API layer

`app.py` uses Python's standard-library HTTP server:

```python
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
```

The `Handler` class processes HTTP requests.

---

## 9.1 Response helper

The `_send()` method serializes Python objects to JSON:

```python
data = json.dumps(body, ensure_ascii=False).encode()
```

It sends:

```text
Content-Type: application/json
Content-Length
Access-Control-Allow-Origin: *
```

The CORS header allows the frontend to communicate with the API.

---

## 9.2 Serving the frontend

Requests to:

```text
/
```

or:

```text
/index.html
```

are handled by:

```python
self._send_html(index_path)
```

This reads the frontend file and sends it with:

```text
Content-Type: text/html
```

---

## 9.3 API routing

The server parses the URL:

```python
url = urlparse(self.path)
params = {
    k: v[0]
    for k, v in parse_qs(url.query).items()
}
```

Then it routes based on `url.path`.

### `/api/categories`

```python
ENGINE.category_tree()
```

Returns the category hierarchy.

### `/api/browse`

```python
ENGINE.browse(cat, sub)
```

Returns documents for the selected category/subcategory.

### `/api/search`

```python
ENGINE.search(q, cat, ftype, k)
```

The query is trimmed and limited to 200 characters:

```python
q = params.get("q", "").strip()[:200]
```

An empty query produces:

```http
400 Bad Request
```

with:

```json
{
  "error": "Missing q"
}
```

### `/api/doc`

The document ID is converted to an integer:

```python
doc_id = int(params.get("id", "0"))
```

Invalid IDs produce:

```http
400 Bad Request
```

Unknown IDs produce:

```http
404 Not Found
```

### `/api/stats`

Returns:

```json
{
  "doc_count": 25,
  "categories": [
    "AI",
    "Cybersecurity",
    "Healthcare",
    "Databases",
    "SoftwareEngineering",
    "IR"
  ],
  "indexed": true
}
```

---

# 10. Frontend layout

The frontend is a single-page application implemented entirely in `index.html`.

It uses:

- HTML
- CSS
- Vanilla JavaScript
- `fetch()`
- Browser `localStorage`
- Browser `sessionStorage`

No frontend framework is used.

---

## 10.1 Main layout

The page uses a three-column layout:

```text
Sidebar | Main results | Detail viewer
```

The sidebar contains:

- Category tree
- Recently viewed documents

The main panel contains:

- Search results
- Browse results
- Filters

The detail panel contains:

- Full document content
- Internal links
- Related documents

The CSS uses a black/yellow theme with custom properties such as:

```css
--yellow: #f5c518;
--bg: #0a0a0a;
--surface: #111111;
```

---

# 11. Frontend JavaScript modules

The JavaScript is organized into logical modules.

---

## 11.1 `Api` module

The `Api` object wraps all backend requests.

Examples:

```javascript
Api.categories()
Api.browse(cat, sub)
Api.search(q, cat, type, k)
Api.doc(id)
Api.stats()
```

For example:

```javascript
search(q, cat, type, k) {
  const params = new URLSearchParams();
  params.set("q", q || "");

  if (cat) params.set("cat", cat);
  if (type) params.set("type", type);

  params.set("k", k || 10);

  return fetch("/api/search?" + params.toString())
    .then(r => r.json());
}
```

`URLSearchParams` ensures that query values are safely URL-encoded.

---

## 11.2 `State` module

The application has one central state object:

```javascript
{
  mode: "browse",
  currentCat: "",
  currentSub: "",
  currentDocId: null,
  filters: {
    cat: "",
    fileType: "",
    keyword: ""
  }
}
```

State can represent:

- Browse mode
- Search mode
- Selected category
- Selected subcategory
- Current document
- Active filters

When the state changes:

```javascript
State.update(...)
```

the global `render()` function is called.

This causes the visible interface to refresh.

The filters object is merged separately so that updating one filter does not remove the others.

---

## 11.3 Global `render()`

The main render function calls:

```javascript
Breadcrumb.render()
SearchBar.render()
ResultsList.render(state)
DocViewer.render(state)
updateRecentlyViewed()
updateNavButtons()
```

This means the UI is derived from the current state instead of each component independently managing unrelated application state.

---

## 11.4 Category menu

The `CategoryMenu` module calls:

```javascript
Api.categories()
```

It builds a collapsible tree:

```text
AI (5)
  Computer Vision (2)
  NLP (1)
  Reinforcement Learning (1)
  Generative Models (1)
```

Clicking a category changes the state:

```javascript
State.update({
  mode: "browse",
  currentCat: catName,
  currentSub: ""
});
```

Clicking a subcategory changes:

```javascript
State.update({
  mode: "browse",
  currentCat: catName,
  currentSub: subName
});
```

On mobile, the hamburger button opens the sidebar and the overlay closes it.

---

## 11.5 Search bar and filters

The search module supports:

- Search submission
- Switching between Search and Browse modes
- Category filtering
- File-type filtering
- Keyword filtering
- Filter chips

When the user submits a search:

```javascript
State.update({
  mode: "search",
  currentDocId: null,
  filters: {
    keyword: q
  }
});
```

The filter controls include:

```text
Category
File Type
Keyword
```

The keyword filter uses a 300 ms debounce so that the interface does not update on every keystroke immediately.

Active filters appear as removable chips, for example:

```text
Category: AI ×
Type: txt ×
Keyword: "neural" ×
```

---

## 11.6 Results list

The `ResultsList` module behaves differently depending on the mode.

### Search mode

It calls:

```javascript
Api.search(
  q,
  state.filters.cat,
  state.filters.fileType,
  20
)
```

The results are displayed in score order.

### Browse mode

It calls:

```javascript
Api.browse(
  state.currentCat,
  state.currentSub
)
```

Then it applies the file-type filter on the frontend.

Each result card displays:

- Title
- Category
- File type
- BM25 score, if available
- Short abstract preview

Cards are keyboard accessible because they have:

```html
tabindex="0"
role="button"
```

Pressing `Enter` or `Space` opens the document.

---

## 11.7 Preview overlay

Hovering over or focusing a result card displays a preview overlay.

The preview includes:

- First 200 characters of the abstract
- Close button
- `Read full document` button

Pressing `Escape` closes the preview.

This allows users to inspect a document without immediately replacing the current detail view.

---

## 11.8 Document viewer

The `DocViewer` module calls:

```javascript
Api.doc(state.currentDocId)
```

It displays:

- Title
- Category
- Subcategory
- File type
- Abstract
- Methodology
- Results
- Internal links
- Related documents

When a document is successfully opened, it is recorded in the recently viewed list:

```javascript
RecentlyViewed.record(doc.id, doc.title)
```

---

## 11.9 Recently viewed documents

Recently viewed documents are stored in browser `localStorage`.

The key is:

```javascript
browse_rv
```

The module:

1. Removes duplicate entries.
2. Adds the newest document at the beginning.
3. Keeps only the latest 10 items.
4. Renders them in the sidebar.

Because `localStorage` is used, the list can remain after the browser is refreshed.

---

## 11.10 Navigation history

Back and forward navigation use `sessionStorage`.

The history stores state snapshots such as:

```javascript
{
  mode: "browse",
  currentCat: "AI",
  currentSub: "NLP",
  currentDocId: 2,
  filters: {
    cat: "",
    fileType: "",
    keyword: ""
  }
}
```

The system maintains:

```text
browse_nav
browse_nav_fwd
```

When a new document is opened:

```javascript
NavHistory.push(State.get())
```

The forward history is cleared because a new navigation path has started.

The interface supports:

- Back button
- Forward button
- `Alt + Left`
- `Alt + Right`

---

## 11.11 Breadcrumbs

The breadcrumb module generates navigation trails such as:

```text
Home
```

```text
Home › AI
```

```text
Home › AI › NLP
```

```text
Home › Search: "neural network"
```

```text
Home › AI › Computer Vision › Deep Neural Networks for Image Classification
```

The breadcrumb links allow the user to return to previous category levels.

---

# 12. Complete request flow example

Suppose the user searches for:

```text
neural network
```

The complete flow is:

### Step 1: User submits search

The search form captures the query and updates state:

```javascript
State.update({
  mode: "search",
  filters: {
    keyword: "neural network"
  }
});
```

### Step 2: Global rendering begins

`render()` calls:

```javascript
ResultsList.render(state)
```

### Step 3: Frontend calls API

```text
GET /api/search?q=neural+network&k=20
```

### Step 4: `app.py` receives request

It extracts:

```python
q = "neural network"
cat = ""
ftype = ""
k = 20
```

### Step 5: Backend search starts

`BrowseEngine.search()` invokes:

```python
self._engine.search(
    query,
    model="bm25",
    k=50
)
```

### Step 6: Query processing occurs

The reusable backend:

1. Tokenizes the query.
2. Removes stop words.
3. Stems terms.
4. Looks up posting lists.
5. Calculates BM25 scores.
6. Sorts documents by score.

### Step 7: Week 5 filtering occurs

Category and file-type filters are applied.

### Step 8: JSON response is returned

The server sends:

```json
{
  "hits": [
    {
      "id": 1,
      "title": "Deep Neural Networks for Image Classification",
      "score": 4.23,
      "category": "AI",
      "file_type": "txt"
    }
  ],
  "total": 1
}
```

### Step 9: Frontend renders cards

The result cards are inserted into:

```html
<div id="results-list">
```

### Step 10: User opens a document

The selected document ID is placed in state:

```javascript
State.update({
  currentDocId: 1
});
```

### Step 11: Full document is fetched

```text
GET /api/doc?id=1
```

### Step 12: Detail panel is rendered

The detail view displays the document and its related/internal links.

---

# 13. Testing

## 13.1 Smoke tests

`test_browse_smoke.py` checks five core behaviors:

### Test 1: Engine initialization

```python
engine = BrowseEngine()
```

Confirms that the corpus and index load successfully.

### Test 2: Six top-level categories

```python
tree = engine.category_tree()
assert len(tree) == 6
```

### Test 3: Category browsing

```python
ai_docs = engine.browse(cat="AI")
```

Every returned document must have:

```python
category == "AI"
```

### Test 4: Search ordering

```python
result = engine.search(query="neural network")
```

The test confirms that scores are non-increasing:

```python
scores[i] >= scores[i + 1]
```

### Test 5: Search category filtering

```python
engine.search(query="test", cat="IR")
```

Every result must belong to the `IR` category.

Run it with:

```powershell
cd "D:\sem\7 Sem\IR\Assignments\Week 5"
python test_browse_smoke.py
```

---

## 13.2 Integration check

`_integration_check.py` verifies:

- `stats()`
- Document count
- Six categories
- Index availability
- Category browsing
- Search ordering
- Full document lookup
- Related document field
- Internal links field

Run it with:

```powershell
python _integration_check.py
```

---

# 14. Important design decisions

## Backend reuse

The Week 5 folder does not duplicate the existing search engine. It imports:

- `InvertedIndex`
- `SearchEngine`
- `STOPWORDS`

This keeps indexing and ranking centralized.

## Separation of responsibilities

The implementation is separated into:

```text
browse.py  → business/domain logic
app.py     → HTTP routing
index.html → user interface
```

This makes the system easier to understand and maintain.

## Lightweight browse responses

Browse results use `_strip_doc()` so that the frontend receives summaries instead of the full document contents.

## Full document responses

The full document endpoint includes methodology and results only when a user opens a specific document.

## Category-aware related search

Documents in the same category receive a `1.5x` score boost, making related results more relevant to the current topic.

## Browser-side navigation

Navigation state is stored in `sessionStorage`, while recently viewed documents are stored in `localStorage`.

---

# 15. Overall summary

The Week 5 system works as follows:

```text
documents.json
      ↓
BrowseEngine initialization
      ↓
Derived categories, subcategories, and file types
      ↓
Inverted index loaded or built
      ↓
SearchEngine created
      ↓
Python HTTP server starts on port 8080
      ↓
Browser loads index.html
      ↓
Frontend calls JSON API endpoints
      ↓
Backend performs browsing, BM25 search, related-document discovery
      ↓
Frontend renders categories, results, documents, and navigation
```

In short, Week 5 implements a **category-based document browsing system combined with ranked IR search**, including:

- Hierarchical categories
- Subcategories
- BM25 search
- Category and file-type filters
- Full document viewing
- Related documents
- Internal links
- Recently viewed history
- Back/forward navigation
- Responsive and keyboard-accessible UI
- Smoke and integration tests