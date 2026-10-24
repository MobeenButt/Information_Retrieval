# Week 6 — Extended Boolean Search

Run from this folder with `python app.py`, then open the `/fyp` URL printed by
the server. The Week 6 app is standalone and does not import Week 5 code.

## Raw data inputs

The app references the repository-level `FYP_Data/` directory by a relative
path (`../FYP_Data` from this folder). It does not copy data into Week 6. At
the time this loader was implemented, it reads:

| Relative input | Documents |
|---|---:|
| `FYP_Data/06_DebugBench/debugbench.jsonl` — streamed one line at a time | 4,253 |
| `FYP_Data/04_Incident_Action_Dataset/PAG-Synthetic-Cloud-Incident-Dataset (2).json` | 950 |
| `FYP_Data/05_Loghub/*/*_2k.log_structured.csv` — streamed one row at a time, 16 files | 32,000 |
| `FYP_Data/07_QuixBugs/**/*.py` and `/**/*.java` | 326 |
| `FYP_Data/*.pdf` — four papers, text extracted with `pypdf` | 4 |
| **Total** | **37,533** |

Malformed JSONL rows and CSV rows with missing cells are skipped and counted
in `/api/fyp-meta`. If a paper cannot be read, that file is skipped and counted.
The checkout does not contain `WEEK5_FYP/FYP_Data`, SWE-bench source files, or
BugsInPy source files, so the loader reports and uses the available raw inputs
above rather than the generated `WEEK5_FYP/fyp_data.json` snapshot.

Every result has `id`, `title`, `text`, `type`, `source`, and `source_file`
fields. The UI shows the file name alongside its score. Extended Boolean
search can be unchecked for a literal text match. The explain option returns
per-term normalized TF-IDF weights and the p-norm expression evaluation.

## Tests

From the repository root: `python -m unittest WEEK6_FYP.test_extended_boolean -v`
