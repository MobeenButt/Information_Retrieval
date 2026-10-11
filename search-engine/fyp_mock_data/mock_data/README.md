# FYP mock dataset (synthetic)

Everything here is generated and fake: people, hosts, keys, e-mail addresses. Reproducible with `python generate_mock_data.py` (fixed seed).

| Path | Content |
|---|---|
| logs/app_logs.jsonl | 5,501 structured log events (JSON Lines), 21 days, 7 services |
| logs/app_logs.log | the same events as plain text, with multi-line stack traces |
| ci/*.txt | 5 GitHub Actions style failed nightly test runs |
| tickets/jira_tickets.json | 45 Jira-style tickets: 15 bugs (BUG-201..215), 12 past incidents (INC-*), 18 other tasks (SHOP-*) |
| commits/commits.json | 64 commits, including the 15 bug-introducing commits and their fixes |
| ground_truth/cases.json | ground truth for injected bugs B01..B15 (commit, root cause, relevant files, relevant log ids) |
| ir/ | corpus.jsonl, queries.jsonl, qrels.tsv (BEIR format, graded relevance 0-2) |

Notes
- Logs contain realistic noise: normal traffic, unrelated errors and slow queries, so retrieval is not trivial.
- qrels were generated from the injected-bug definitions, not tuned on any model.
- Treat results on this data as a development test. Use real public data and your own sample app for final claims.
