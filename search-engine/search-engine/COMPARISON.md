# Model Comparison

This document compares the core IR models implemented in this project and ends
with a recommendation for the FYP (AI-Powered Bug Investigation Platform).

## Comparison table

| Pair | Dimension | Model A | Model B |
|---|---|---|---|
| **Boolean vs BIM** | Matching | Exact set membership (term present/absent) | Probabilistic weight from relevance odds (RSJ) |
| | Output | Unranked set of docs (score = 1) | Ranked list with a relevance probability |
| | Term weighting | None — all terms equal | RSJ weight = ln[(r+0.5)(N−n+0.5)/((n−r+0.5)(R−r+0.5))] |
| | Feedback | Not supported | Supported via R (relevant set) and r (relevant with term) |
| | Best for | Precise filtering (must contain X AND Y) | Ranking when some relevance judgements exist |
| **BIM vs BM25** | Term frequency | Ignored (binary presence) | Used with saturation k1 |
| | Doc length | Ignored | Normalised by b·|d|/avgdl |
| | Weight form | RSJ log-odds | idf · tf(k1+1)/(tf + k1(1−b+b·|d|/avgdl)) |
| | Assumption | Binary independence | Term-frequency saturation, length normalised |
| | Behaviour | Flat, can over-weight rare terms | Robust, the de-facto standard ranking function |
| **Overlap vs BM25** | Score | |Q ∩ D| — count of shared terms | Sum of weighted BM25 term scores |
| | Term importance | All terms equal weight | Rare terms (high idf) count more |
| | Term frequency | Ignored | Included with diminishing returns |
| | Doc length | Ignored | Normalised |
| | Result | Quick baseline, weak ranking | Strong, well-calibrated ranking |
| **TF-IDF vs BM25** | Family | Vector Space Model (cosine) | Probabilistic (Okapi family) |
| | tf weighting | 1 + ln(tf), linear in log | tf(k1+1)/(tf + norm), saturating |
| | Length norm | Cosine divides by vector norm | Explicit b·|d|/avgdl factor |
| | Geometry | Angle between vectors | Sum of independent term contributions |
| | Empirics | Good, but beaten by BM25 on most TREC runs | Usually the stronger keyword ranker |

## Boolean vs BIM

The Boolean model treats a query as a logical expression and returns the exact
set of documents that satisfy it. Every match is equally relevant (score 1),
there is no term weighting, and the user must think in `AND / OR / NOT`. The
Binary Independence Model keeps the binary presence assumption but replaces
the set logic with a *weight* for each term — the Robertson-Sparck Jones weight
— and sums those weights to rank documents. BIM also accepts relevance feedback
(R, r), so a few judged documents sharpen the weights. In short: Boolean is
about *which* documents qualify; BIM is about *how likely* each qualifying
document is relevant.

## BIM vs BM25

BIM is the conceptual parent of BM25. Its weakness is the binary-independence
assumption: a term is either present or not, so a document mentioning a term ten
times scores the same as one mentioning it once, and long documents are not
penalised. BM25 drops both assumptions. It uses term frequency with saturation
(controlled by k1, so the tenth occurrence adds less than the first) and
document-length normalisation (controlled by b, so a long doc does not win just
by being long). The idf is similar in spirit but BM25's is the form used by
Lucene/Elasticsearch. BM25 almost always beats BIM empirically, which is why
BIM is taught as theory and BM25 is deployed in production.

## Overlap vs BM25

The overlap model scores a document by the count of query terms it contains
(|Q ∩ D|). It is the simplest possible ranker: fast, transparent, and a useful
baseline, but it ignores everything that matters for ranking — term importance,
term frequency, and document length. BM25 incorporates all three: rare terms
contribute more through idf, repeated terms saturate through k1, and length is
normalised through b. Overlap can rank a document that mentions three common
query words above one that mentions one rare, decisive word; BM25 will not.

## TF-IDF vs BM25

Both are ranked models, but from different families. TF-IDF belongs to the
Vector Space Model: documents and the query are vectors and ranking is by the
cosine of the angle between them. The tf weight 1 + ln(tf) grows without bound
and length is handled implicitly through cosine normalisation. BM25 is
probabilistic: it sums independent term contributions, uses a saturating
tf function so frequency flattens out, and normalises length explicitly. On
most retrieval benchmarks BM25 outperforms basic TF-IDF; TF-IDF remains
valuable as a feature for learning-to-rank and as the document representation
for clustering.

## FYP recommendation (AI-Powered Bug Investigation Platform)

For the FYP corpus — logs, code chunks, commits and tickets — I recommend a
**two-stage retrieval pipeline** with **BM25 as the first-stage ranker**.

1. **First stage — BM25 over the structured fields.** Bug evidence items are
   naturally structured (a ticket has title/summary, a commit has message and
   diff, a log has level and text). Use field-weighted BM25 (title/message
   boosted) so that a rare function name in a commit message outranks a common
   word repeated in a log. BM25 is robust, needs no training, and is what the
   platform can run on every incoming bug report in real time.

2. **Second stage — BIM-style relevance feedback, then a cross-encoder.**
   When a developer marks a result as relevant, feed it back into BIM's RSJ
   weights (R, r) so subsequent similar bugs are re-ranked. For the top 20
   candidates, a small cross-encoder re-ranks with fine-grained semantics. This
   mirrors the hybrid (BM25 + dense/RRF) architecture from Week 2 and is the
   path most likely to maximise MRR/nDCG on the evidence items.
