# Presentation Outline — AI-Powered Bug Investigation Platform (IR Module)

Eight sections. Each lists a slide title, 3-5 bullets, speaker notes, and what
to show live.

## 1. FYP Problem

- Software bugs leave evidence scattered across logs, code chunks, commits, and tickets.
- Developers must manually sift these disconnected sources to diagnose one bug.
- This is slow, repetitive, and error-prone for large repositories.
- The FYP builds an AI platform that gathers and ranks the evidence for a bug automatically.
- The IR module is the engine that retrieves which evidence items matter for a given bug.

**Speaker notes:** Frame the pain point first. Bugs are not solved by one file;
they live across logs, commits, and tickets. Stress that retrieval is the
foundation: every later AI step (summarising, fixing) depends on retrieving the
right evidence first.

**Show live:** Open a sample bug report and the four raw evidence sources side by
side to make the "scattered evidence" problem visible.

## 2. Retrieval Requirement

- Corpus: 13-30 software evidence items (logs, code chunks, commits, tickets).
- Must support natural-language queries derived from a bug description.
- Must rank relevant evidence at the top and explain why it ranked there.
- Must work across structured fields (ticket title vs commit message vs log text).
- Must be measurable with Precision@k, Recall@k, MRR, and nDCG.

**Speaker notes:** Define the requirement crisply. The corpus is small but
structured, so field-aware retrieval and explainability matter as much as raw
ranking quality. Emphasise that evaluation metrics are part of the requirement,
not an afterthought.

**Show live:** The relevance_judgments.json file with five judged queries and
the metric list (Precision, Recall, MRR, nDCG).

## 3. Selected IR Model

- Primary ranker: Okapi BM25 with field weighting (title/message boosted).
- Justification: robust, no training needed, runs in real time, the production standard.
- BIM with relevance feedback used to re-weight terms once a developer marks results.
- Boolean retrieval reserved for precise filtering (must contain X AND Y).
- Structured retrieval (overlap / non-overlap / proximal nodes) for field-aware matching.

**Speaker notes:** Explain why BM25 over a learned model: the corpus is small,
labels are scarce, and BM25 is the ranker behind Lucene/Elasticsearch. BIM adds
learning-through-feedback without needing a training set.

**Show live:** The COMPARISON.md recommendation paragraph and the model list in
the Search tab of the Streamlit app.

## 4. Implementation

- Pipeline: tokenize -> remove stop-words -> Porter-style stem, applied to docs and queries.
- Positional inverted index plus a per-field index (title, abstract, method, results).
- Recursive-descent Boolean parser with precedence NOT > AND > OR and parentheses.
- TF-IDF Vector Space Model, BIM (RSJ weights + sigmoid probability), and field-weighted BM25.
- Structured retrieval: overlap, non-overlap, and proximal-node scoring with explanations.

**Speaker notes:** Walk the architecture. Stress one shared preprocessing pipeline
so document terms and query terms align. The index is positional (for proximity)
and fielded (for structured search).

**Show live:** The Pipeline View tab for one query and a snippet of the inverted
index from a Python REPL.

## 5. Example Queries

- Query 1: "machine learning intrusion detection" (Cybersecurity focus).
- Query 2: "neural network image classification" (AI focus).
- Query 3: "information retrieval search ranking" (IR focus).
- Query 4: "best treatment for diabetes" (Healthcare, full BM25 walkthrough).
- Query 5: "bug investigation software repositories" (FYP-aligned, Software Engineering).

**Speaker notes:** These five queries span every category and include the FYP
theme (query 5). Query 4 is the centerpiece because it shows the full BM25 math.

**Show live:** Run demo_queries.py and pause on Query 4's per-term BM25
walkthrough (tf, idf, length normalisation, term score, total).

## 6. Results

- BM25, VSM, and field-weighted BM25 reach Recall@5 = 1.0 and MRR = 1.0 on the diabetes query.
- Field-weighted BM25 and VSM lead on mean average precision across all five queries.
- Boolean retrieval is precise but unranked, so it trails on MRR (0.7) versus 1.0.
- BIM lags slightly without relevance feedback but improves once feedback is added.
- Proximal nodes surface documents where query terms co-occur in nearby fields.

**Speaker notes:** Present the comparison table, then highlight two stories:
why Boolean is precise but unrankable, and why BM25 dominates once length
normalisation is included. Tie proximal nodes back to the FYP (terms co-occurring
in a commit message and a log is a strong bug signal).

**Show live:** The Evaluation tab: the Markdown comparison table and the
Precision@5 vs Recall@5 bar chart.

## 7. Comparison

- Boolean vs BIM: exact sets vs probabilistic ranking with feedback.
- BIM vs BM25: binary independence vs term-frequency saturation and length normalisation.
- Overlap vs BM25: equal-weight count vs idf-weighted, length-normalised score.
- TF-IDF vs BM25: cosine geometry vs probabilistic saturation; BM25 wins on most benchmarks.
- Recommendation: field-weighted BM25 first stage, BIM feedback, cross-encoder re-rank second.

**Speaker notes:** Use the COMPARISON.md table. Keep the message simple: each
pair trades one weakness for one strength, and the FYP picks the combination
that minimises weaknesses for a small, structured, feedback-rich corpus.

**Show live:** The Compare Models tab with the mean-metrics bar chart and the
side-by-side table.

## 8. Conclusion

- The IR module retrieves and ranks bug evidence across logs, code, commits, and tickets.
- Field-weighted BM25 plus structured retrieval meets the retrieval requirement with MRR 1.0.
- Relevance feedback (BIM) and proximal nodes add learning and locality for free.
- Evaluation with Precision, Recall, MRR, and nDCG proves the choice objectively.
- Next step: add a dense-vector / cross-encoder second stage for semantic re-ranking.

**Speaker notes:** Close by restating the requirement, the chosen model, and the
evidence. End on the forward path: BM25 first stage plus a neural re-ranker is the
hybrid architecture from Week 2 and the natural FYP extension.

**Show live:** The Filtering Demo tab to show the standing-profile (push) model,
then the full Search tab with show_math enabled to close on the BM25 walkthrough.
