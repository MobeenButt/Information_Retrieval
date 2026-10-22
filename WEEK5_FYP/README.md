# FYP evidence browser

This is the FYP-facing data layer and dashboard. It uses the complete
`FYP_Data` folder, not a small assignment-only example.

## Data pipeline

Run this whenever either source dataset changes:

```powershell
cd "D:\sem\7 Sem\IR\Assignments\WEEK5_FYP"
python build_fyp_data.py
```

The builder:

1. Reads SWE-bench JSONL and validates it against its Parquet copy.
2. Reads the synthetic cloud incident/action JSON.
3. Reads every DebugBench JSONL record.
4. Reads every BugsInPy bug descriptor and patch from the archive.
5. Reads every structured LogHub CSV row.
6. Reads QuixBugs Python/Java source artifacts.
7. Registers the research PDFs as navigable source documents.
8. Converts everything into the FYP Incident/Evidence/Claim/Graph schema.

The current generated dataset contains 6,350 Incidents and 57,061 Evidence
records across these categories:

- SWE Bench
- Incident Action Reports
- DebugBench
- BugsInPy
- LogHub
- QuixBugs
- Research Documents

Each category is a real hierarchy node. Every incident contains explicit
evidence nodes, claim links, and ordered `related_artifact` edges. The output
also contains a `hierarchy` array with category counts and incident IDs.

## FYP schema mapping

| Source field | FYP field |
|---|---|
| `instance_id` | `Incident.id` and `Evidence.incident_id` |
| `problem_statement` | Jira Evidence content and incident title |
| `repo` | `Incident.repository`, Evidence source |
| `base_commit` | `Incident.commit`, commit Evidence |
| `patch` | code and commit Evidence |
| `FAIL_TO_PASS` | failing-to-passing test Evidence |
| `PASS_TO_PASS` | regression test Evidence |
| `eval_script`, `log_parser` | log Evidence |
| `hints_text` | Slack/notes Evidence |
| repository/commit/test relationships | Knowledge Graph nodes and edges |

## Run the FYP dashboard

```powershell
cd "D:\sem\7 Sem\IR\Assignments\Week 5"
python app.py
```

Open:

```text
http://127.0.0.1:8080/fyp
```

The data API is:

```text
http://127.0.0.1:8080/api/fyp-data
```

The dashboard supports:

- Selecting a category and then an incident.
- Viewing all categories or all incidents.
- Filtering categories and incidents by ID.
- Searching all normalized evidence content.
- Filtering by code, issue, test, commit, log, notes, or graph evidence.
- Opening an evidence preview with its incident, locator, claim, and graph links.
- Clicking related documents to navigate internally.
- Using **Discover related evidence** to jump to a linked artifact without
  choosing a predetermined path (opportunistic browsing).
- Responsive desktop, tablet, and mobile layouts.

The generated `fyp_data.json` is intentionally used as a runtime snapshot so
the server does not require Parquet dependencies every time it starts. The
source files are fully used during the build/validation step, and the
rebuild command keeps the snapshot synchronized.
