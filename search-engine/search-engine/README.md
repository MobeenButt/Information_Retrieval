# Mini Search Engine (Information Retrieval, Week 1, IR Track)

A complete document search engine that indexes, searches and ranks a small text
collection. It follows the retrieval pipeline from the Week 1 lecture:

```
User -> Query -> Text Processing -> Indexing -> Searching -> Ranking -> Results
```

**Requirements:** Python 3.8+ only. No packages to install.

## Run it

```bash
python backend/app.py          # then open http://localhost:8000
python backend/app.py --port 9000      # different port
python backend/app.py --reindex        # force rebuild of the index
python backend/cli.py "inverted index" --model bm25 --mode all   # terminal search
python backend/tests.py                # unit tests
```

## Project layout

```
search-engine/
├── data/               25 sample documents (.txt). First line: "Title: ...". Add your own!
├── backend/
│   ├── preprocess.py   tokenize -> remove stop-words -> stem
│   ├── indexer.py      inverted index + statistics, save/load (index/index.json)
│   ├── ranker.py       TF-IDF (cosine-normalised) and BM25
│   ├── engine.py       SearchEngine: query -> results, snippets, pipeline trace
│   ├── app.py          HTTP server + JSON API (standard library)
│   ├── cli.py          command-line search
│   └── tests.py        unit tests
├── frontend/index.html search page (HTML/CSS/JS)
├── make_data.py        script that generated the sample documents
└── README.md
```

## How it works (mapped to the lecture)

| Lecture step | Where | What happens |
|---|---|---|
| Text processing | `preprocess.py` | Lowercase and split into tokens, drop stop-words (the, is, of), stem (running -> run). Applied to documents **and** queries. |
| Indexing | `indexer.py` | Builds the inverted index `term -> {doc_id: term frequency}`, e.g. `index -> {2: 5, 3: 1}`. Title words count twice. Also stores document lengths and vector norms. |
| Searching | `engine.py` | Processes the query the same way, looks each term up in the index and collects candidate documents. "Match all words" keeps only documents containing every term (boolean AND). |
| Ranking | `ranker.py` | Scores every candidate and sorts by score (see below). |
| Results | `engine.py` + frontend | Title, score, highlighted snippet, matched terms, and the full text on click. |

### Ranking formulas

**TF-IDF (default)**: the "more meaningful shared terms -> higher rank" idea from slide 17.

```
tf-weight(t, d) = 1 + ln(tf)          idf(t) = ln(1 + N / df)
score(q, d)     = sum over query terms of [ (1+ln qtf)*idf ] * [ (1+ln tf)*idf ]  /  |d|
```
`|d|` is the length of the document's TF-IDF vector, so long documents don't win just by being long.

**BM25** (the function used by Lucene/Elasticsearch):

```
score(q, d) = sum idf(t) * tf*(k1+1) / ( tf + k1*(1 - b + b*|d|/avgdl) )     k1=1.5, b=0.75
```
Repeated terms add less and less (saturation) and long documents are normalised.

## API

| Request | Response |
|---|---|
| `GET /search?q=machine+learning&model=tfidf&mode=any&k=10` | `{query, trace:{tokens,no_stop,stems,lookups}, total, hits:[{id,title,score,snippet,matched}], took_ms}` |
| `GET /doc?id=3` | `{id, title, text}` |
| `GET /stats` | `{documents, terms, avg_doc_length}` |

## Using your own documents

Put `.txt` files in `data/` (first line `Title: Your title`) and restart the server.
The index is rebuilt automatically when a document is newer than `index/index.json`.

## Ideas for your report

1. Show the pipeline for one query (the UI's "What the engine did" panel is a ready-made screenshot).
2. Print part of the inverted index and explain a postings list.
3. Compare TF-IDF and BM25 on 5 queries: where do the rankings differ and why?
4. Compare "any" vs "all": effect on precision and recall.
5. Known limits and next steps: simple stemmer (compute vs computing differ), no phrase search,
   no synonyms (query expansion), no semantic matching (embeddings / FAISS, Week 2+).
