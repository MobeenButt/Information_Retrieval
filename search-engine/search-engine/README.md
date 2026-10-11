# IR Search Engine — AI-Powered Bug Investigation Platform

A complete Information Retrieval system for the FYP track (AI-Powered Software
Bug Investigation and Resolution Platform). It indexes a structured corpus of
research-paper documents and implements classical, probabilistic, vector-space,
and structured retrieval models, plus classification, clustering, filtering, and
full evaluation.

This is the advanced `src/` system. The original Week 1 `backend/` (flat-file
search engine) is unchanged and still works alongside it.

## Pipeline

```
User query -> tokenize -> remove stop-words -> stem -> inverted index lookup
          -> ranking (Boolean / VSM / BM25 / BIM / overlap / proximal / field BM25)
          -> category filter -> ranked results
```

## Folder structure

```
search-engine/
├── data/
│   ├── documents.json          25 structured research-paper documents (the corpus)
│   ├── relevance_judgments.json 5 queries with relevant doc ids (for evaluation)
│   └── 01_*.txt .. 28_*.xml    original flat-file corpus used by backend/
├── src/                        the advanced IR system (all from scratch)
│   ├── text_processing.py      tokenize / remove_stopwords / Porter-style stem
│   ├── indexing.py              positional + per-field inverted index, save/load
│   ├── boolean_model.py        Boolean parser (NOT > AND > OR, parentheses)
│   ├── vector_space_model.py    TF-IDF vectors + cosine similarity (VSM)
│   ├── probabilistic_models.py  sigmoid, RSJ/BIM, BM25 score + explain
│   ├── structured_retrieval.py  field BM25, overlap, non-overlap, proximal nodes
│   ├── classification_clustering.py Naive Bayes classification, k-means clustering
│   ├── filtering.py             ad-hoc search vs profile filtering
│   ├── evaluation.py            Precision/Recall/AP/MRR/nDCG + comparison table
│   └── search_engine.py         SearchEngine facade + pipeline trace
├── tests/                      pytest suite (imports from src/)
├── app.py                      Streamlit UI (6 tabs)
├── demo_queries.py             5 queries x 8 models + full BM25 walkthrough
├── requirements.txt            pinned dependencies
├── COMPARISON.md               model-vs-model comparison + FYP recommendation
├── FEYNMAN.md                  plain-language explanations (10 sections)
├── PRESENTATION_OUTLINE.md     8-section presentation outline
└── README.md                   this file
```

## Setup

Python 3.8+ (tested on 3.13). Install the pinned dependencies:

```bash
pip install -r requirements.txt
```

Dependencies: `streamlit`, `numpy`, `scikit-learn`, `nltk`.

## How to run

```bash
# Streamlit UI (6 tabs: Search, Compare, Pipeline, Evaluation, Classification, Filtering)
streamlit run app.py

# Demo: 5 queries through every model + full BM25 math for query 4
python demo_queries.py

# Test suite (imports from src/, not backend/)
python -m pytest tests/ -v

# Quick sanity checks
python -c "import sys; sys.path.insert(0,'src'); from text_processing import analyze_pipeline; print(analyze_pipeline('The running machines'))"
python -c "import sys; sys.path.insert(0,'src'); from probabilistic_models import verify_sigmoid_example; print(verify_sigmoid_example())"
python -c "import sys; sys.path.insert(0,'src'); from vector_space_model import verify_slide_example; print(verify_slide_example())"
```

## Concept-to-file map

| Week | Concept | File | Function |
|---|---|---|---|
| 1 | Text processing | `src/text_processing.py` | `tokenize`, `remove_stopwords`, `stem`, `analyze_pipeline` |
| 1 | Inverted index | `src/indexing.py` | `InvertedIndex.add_document`, `finalize`, `forward_index` |
| 2 | Ad-hoc vs filtering | `src/filtering.py` | `adhoc_search`, `stream_filter`, `UserProfile` |
| 3 | Boolean retrieval | `src/boolean_model.py` | `parse_and_execute`, `boolean_search` |
| 3 | Vector space model | `src/vector_space_model.py` | `vsm_search`, `cosine_similarity`, `verify_slide_example` |
| 3 | Classification & clustering | `src/classification_clustering.py` | `classify_documents`, `cluster_documents` |
| 3 | Evaluation | `src/evaluation.py` | `evaluate_all_models`, `print_comparison_table` |
| 4 | Probabilistic models | `src/probabilistic_models.py` | `sigmoid`, `rsj_weight`, `bim_search`, `bm25_search`, `bm25_explain` |
| 4 | Structured retrieval | `src/structured_retrieval.py` | `field_bm25_search`, `overlapped_lists`, `non_overlapped_lists`, `proximal_nodes` |
| - | Engine facade | `src/search_engine.py` | `SearchEngine.search`, `pipeline_trace` |

## Deliverables checklist

- [x] `data/documents.json` — 25 structured docs (AI 5, Cybersecurity 5, Healthcare 5, Databases 4, SoftwareEngineering 3, IR 3)
- [x] `src/text_processing.py` — from-scratch tokeniser, stop-words, Porter-style stem
- [x] `src/indexing.py` — positional + per-field inverted index, JSON + folder loaders
- [x] `src/boolean_model.py` — full Boolean parser (NOT > AND > OR, parentheses)
- [x] `src/vector_space_model.py` — TF-IDF VSM + slide example (0.816 / 0.408 / 0.000)
- [x] `src/probabilistic_models.py` — sigmoid (0.9707/0.8808/0.9918), RSJ/BIM, BM25 + explain
- [x] `src/structured_retrieval.py` — field BM25, overlap, non-overlap, proximal nodes
- [x] `src/classification_clustering.py` — Naive Bayes + k-means (scikit-learn)
- [x] `src/filtering.py` — ad-hoc search vs profile filtering
- [x] `src/evaluation.py` — Precision/Recall/AP/MRR/nDCG + Markdown comparison
- [x] `src/search_engine.py` — `SearchEngine` facade + pipeline trace
- [x] `app.py` — Streamlit UI with 6 tabs
- [x] `demo_queries.py` — 5 queries x 8 models + full BM25 walkthrough
- [x] `tests/` — pytest suite (slide examples, boolean, BM25, TF-IDF, stemming, BIM)
- [x] `requirements.txt` — pinned dependencies
- [x] `COMPARISON.md`, `FEYNMAN.md`, `PRESENTATION_OUTLINE.md`, `README.md`

## Dataset description

`data/documents.json` contains 25 research-paper-style documents. Each document
has `id`, `title`, `abstract` (3-4 sentences), `methodology` (2-3 sentences),
`results` (2-3 sentences), and `category`. Categories and counts:

| Category | Count | Topic examples |
|---|---|---|
| AI | 5 | neural networks, transformers, CNNs, RL, GANs |
| Cybersecurity | 5 | intrusion detection, malware, post-quantum crypto, anomaly, vulnerability |
| Healthcare | 5 | diabetes treatment (x3), cancer diagnosis, drug discovery |
| Databases | 4 | NoSQL, query optimization, distributed DB, data warehousing |
| SoftwareEngineering | 3 | bug investigation, bug localization, code review |
| IR | 3 | learning to rank, document clustering, query expansion |

Design choices for evaluation: documents 11, 12, and 13 all cover diabetes
treatment, so the query "best treatment for diabetes" has 2-3 clearly relevant
documents. Documents 11 and 12 are near-duplicates on the diabetes-treatment
sub-topic; document 8 (post-quantum cryptography) is an off-topic document that
shares no terms with the diabetes query. Shared terms across categories (e.g.
"machine learning", "neural network", "information retrieval") make the models
produce meaningful overlapping candidate sets. The FYP theme is represented by
the SoftwareEngineering docs (bug investigation, bug localization), which tie the
corpus to the AI-Powered Bug Investigation Platform.
