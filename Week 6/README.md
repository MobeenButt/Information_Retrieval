# Week 6 — Extended Boolean Search

Run from this folder with `python app.py`, then open the `/fyp` URL printed by
the server. The Week 6 app is standalone and does not import Week 5 code.

## Raw data inputs

The app references the repository-level `FYP_Data/` directory by a relative
path (`../FYP_Data` from this folder). It does not copy data into Week 6. At
the time this loader was implemented, it reads:

| Relative input | Documents |
|---|---:|
| `FYP_Data/01_SWE_Bench/swebench_lite.jsonl` — streamed one line at a time | 300 |
| `FYP_Data/02_BugsInPy/BugsInPy-master.zip` — indexed from archive descriptors and patches | 501 |
| `FYP_Data/06_DebugBench/debugbench.jsonl` — streamed one line at a time | 4,253 |
| `FYP_Data/04_Incident_Action_Dataset/PAG-Synthetic-Cloud-Incident-Dataset (2).json` | 950 |
| `FYP_Data/05_Loghub/*/*_2k.log_structured.csv` — streamed one row at a time, 16 files | 32,000 |
| `FYP_Data/07_QuixBugs/**/*.py` and `/**/*.java` | 326 |
| `FYP_Data/*.pdf` — four papers, indexed by traceable filename/source metadata | 4 |
| **Total** | **38,334** |

Malformed JSONL rows and CSV rows with missing cells are skipped and counted
in `/api/fyp-meta`. PDFs are indexed as lightweight source documents so large
papers cannot block server startup; their file paths and titles remain searchable.
All assignments use the repository-level `FYP_Data/` folder. The loader does
not use the generated `WEEK5_FYP/fyp_data.json` snapshot.

Every result has `id`, `title`, `text`, `type`, `source`, and `source_file`
fields. The UI shows the file name alongside its score. Extended Boolean
search can be unchecked for a literal text match. The explain option returns
per-term normalized TF-IDF weights, the p-norm expression evaluation, and the
production reranking components: Boolean score, BM25 score, proximity score,
and partial coverage. The live API uses the combined reranker with weights
`0.55 Boolean + 0.25 BM25 + 0.10 proximity + 0.10 coverage`.

The filter controls support file type, source substring, minimum score,
required terms, excluded terms, and explicit include/exclude document IDs.
The dedicated `WEEK6_FYP/query_parser.py` module exposes the parser API while
`extended_boolean.py` retains backward-compatible imports for the original
tests.

## Tests

From the repository root: `python -m unittest WEEK6_FYP.test_extended_boolean -v`
