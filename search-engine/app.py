"""Streamlit UI — IR Search Engine + FYP Mock Data Evaluation.

Run:  streamlit run app.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import pandas as pd
import streamlit as st

from boolean_model import boolean_search, parse_and_execute
from classification_clustering import classify_documents, cluster_documents
from evaluation import evaluate_all_models
from filtering import UserProfile, demo_filtering
from fyp_evaluation import ALL_MODELS, evaluate_all, load_saved_results, run_model
from fyp_loader import build_fyp_index, load_queries, load_qrels, translate_results
from indexing import InvertedIndex
from probabilistic_models import bim_search, bm25_search, bm25_explain, verify_sigmoid_example
from search_engine import SearchEngine
from structured_retrieval import (field_bm25_search, non_overlapped_lists,
                                  overlapped_lists, proximal_nodes)
from text_processing import analyze_pipeline
from vector_space_model import vsm_search, vsm_explain, verify_slide_example

# ─── page config ──────────────────────────────────────────────
st.set_page_config(
    page_title="IR Search Engine — FYP",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── custom CSS ───────────────────────────────────────────────
st.markdown("""
<style>
/* ── main background & text ── */
.stApp { background: #0d0d0d; }

/* ── top bar ── */
header[data-testid="stHeader"] { background: #111 !important; }

/* ── sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #111 0%, #1a1a1a 100%);
    border-right: 1px solid #2a2a2a;
}
[data-testid="stSidebar"] * { color: #e0e0e0 !important; }

/* ── metric cards ── */
div[data-testid="metric-container"] {
    background: #1a1a1a;
    border: 1px solid #f5c518;
    border-radius: 8px;
    padding: 12px 16px;
    box-shadow: 0 0 14px rgba(245,197,24,0.12);
}
div[data-testid="metric-container"] label { color: #aaa !important; font-size: 0.78rem; }
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #f5c518 !important; font-size: 1.4rem; font-weight: 700;
}

/* ── dataframes ── */
.stDataFrame { border: 1px solid #2a2a2a !important; border-radius: 8px; }
thead tr th { background: #1a1a1a !important; color: #f5c518 !important; }
tbody tr:hover td { background: #1e1e1e !important; }

/* ── tabs ── */
button[data-baseweb="tab"] {
    background: #1a1a1a !important;
    border-radius: 6px 6px 0 0 !important;
    color: #888 !important;
    font-weight: 600;
    border: 1px solid #2a2a2a !important;
    margin-right: 4px;
}
button[data-baseweb="tab"][aria-selected="true"] {
    background: #f5c518 !important;
    color: #000 !important;
    border-color: #f5c518 !important;
}

/* ── result cards ── */
.result-card {
    background: #151515;
    border: 1px solid #2a2a2a;
    border-left: 4px solid #f5c518;
    border-radius: 6px;
    padding: 14px 16px 10px;
    margin-bottom: 10px;
    transition: box-shadow 0.2s;
}
.result-card:hover { box-shadow: 0 4px 20px rgba(245,197,24,0.18); border-left-color: #ffd740; }
.result-rank { font-size: 0.78rem; color: #666; float: right; }
.result-title { color: #f5c518; font-weight: 700; font-size: 1.02rem; margin-bottom: 4px; }
.result-meta { font-size: 0.78rem; color: #888; margin-top: 6px; }
.result-snippet { font-size: 0.85rem; color: #ccc; margin: 6px 0; }
.badge {
    display: inline-block; padding: 2px 8px; border-radius: 10px;
    font-size: 0.72rem; font-weight: 600; margin-right: 4px;
}
.badge-log     { background: #1a2a1a; color: #6f6; border: 1px solid #2a4a2a; }
.badge-commit  { background: #1a1a2a; color: #88f; border: 1px solid #2a2a4a; }
.badge-code    { background: #2a1a1a; color: #f88; border: 1px solid #4a2a2a; }
.badge-ticket  { background: #2a2a1a; color: #ff8; border: 1px solid #4a4a2a; }
.badge-schema  { background: #1a2a2a; color: #8ff; border: 1px solid #2a4a4a; }
.badge-best    { background: #f5c518; color: #000; border: 1px solid #f5c518; }

/* ── score bar ── */
.score-bar-bg { background: #2a2a2a; height: 3px; border-radius: 2px; margin: 6px 0; }
.score-bar-fill { height: 100%; background: linear-gradient(90deg,#f5c518,#ffd740); border-radius: 2px; }

/* ── section headers ── */
.section-header {
    font-size: 1.35rem; font-weight: 700;
    color: #f5c518; margin: 8px 0 16px;
    border-bottom: 2px solid #f5c518;
    padding-bottom: 6px;
}
.sub-header { font-size: 1rem; color: #ccc; margin: 12px 0 8px; font-weight: 600; }

/* ── pipeline step ── */
.pipeline-step {
    background: #1a1a1a; border-left: 3px solid #f5c518;
    border-radius: 0 6px 6px 0; padding: 10px 14px; margin-bottom: 8px;
}
.pipeline-step .step-name { color: #f5c518; font-weight: 600; font-size: 0.88rem; }
.pipeline-step .step-val  { color: #ccc; font-size: 0.84rem; }

/* ── comparison table colours ── */
.val-best { color: #69ff47 !important; font-weight: 700; }
.val-mid  { color: #ffd740 !important; }
.val-low  { color: #ff5252 !important; }

/* ── general text ── */
p, li, span, div { color: #ccc; }
h1,h2,h3,h4 { color: #f5c518 !important; }
code { background: #1e1e1e !important; color: #f5c518 !important; border-radius: 4px; padding: 1px 5px; }
</style>
""", unsafe_allow_html=True)

# ─── cached resources ──────────────────────────────────────────
@st.cache_resource(show_spinner="Building research-paper index…")
def get_research_engine():
    return SearchEngine(
        data_path="data/documents.json",
        index_path="index/structured_index.json",
    )

@st.cache_resource(show_spinner="Building FYP mock-data index…")
def get_fyp_index():
    return build_fyp_index(force=False)

@st.cache_data(show_spinner=False)
def get_fyp_queries():
    return load_queries()

@st.cache_data(show_spinner=False)
def get_fyp_qrels():
    return load_qrels()

@st.cache_data(show_spinner="Running FYP evaluation (8 models × 15 queries)…")
def run_fyp_evaluation():
    return evaluate_all(k=10, force_reindex=False)

# ─── helpers ──────────────────────────────────────────────────
def _type_badge(doc_type: str) -> str:
    cls = {"log": "badge-log", "commit": "badge-commit", "code": "badge-code",
           "ticket": "badge-ticket", "schema_change": "badge-schema"}.get(doc_type, "badge-ticket")
    return f'<span class="badge {cls}">{doc_type.upper()}</span>'

def render_result_card(hit: dict, rank: int, top_score: float,
                       show_corpus_id: bool = False):
    score      = hit.get("score", 0)
    title      = hit.get("title") or hit.get("corpus_id", f"Doc {hit.get('id','')}")
    doc_type   = hit.get("type", "")
    corpus_id  = hit.get("corpus_id", "")
    pct        = int(100 * score / top_score) if top_score else 0
    snippet    = ""
    src_idx    = hit.get("id", "")

    bar = f'<div class="score-bar-bg"><div class="score-bar-fill" style="width:{pct}%"></div></div>'
    badge = _type_badge(doc_type) if doc_type else ""
    id_str = f'<code>{corpus_id}</code>' if show_corpus_id else f'<code>{src_idx}</code>'

    st.markdown(f"""
    <div class="result-card">
      <span class="result-rank">#{rank}</span>
      <div class="result-title">{title or corpus_id}</div>
      {bar}
      <div class="result-meta">
        {badge}{id_str}
        &nbsp;·&nbsp; Score: <b style="color:#f5c518">{score}</b>
        &nbsp;·&nbsp; Matched: <code>{', '.join(hit.get('matched', []))}</code>
      </div>
    </div>
    """, unsafe_allow_html=True)

def color_metric(val, best_val, worst_val):
    if best_val == worst_val:
        return f"{val:.4f}"
    ratio = (val - worst_val) / (best_val - worst_val) if best_val != worst_val else 0
    if ratio >= 0.85:
        return f'<span class="val-best">{val:.4f} ★</span>'
    if ratio >= 0.50:
        return f'<span class="val-mid">{val:.4f}</span>'
    return f'<span class="val-low">{val:.4f}</span>'


# ══════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🔍 IR Search Engine")
    st.markdown("*AI-Powered Bug Investigation*")
    st.markdown("---")

    nav = st.radio("Navigate", [
        "🔎 Search (Research Papers)",
        "🐛 FYP Search (Mock Data)",
        "📊 FYP Model Comparison",
        "🔬 Pipeline Trace",
        "📐 Slide Verification",
        "🏷️ Classification & Clustering",
        "📬 Filtering Demo",
    ])
    st.markdown("---")
    st.markdown("**Models available**")
    for m in ["BM25", "VSM (TF-IDF)", "BIM", "Boolean", "Overlap",
              "Non-Overlap", "Proximal Nodes", "Field BM25"]:
        st.markdown(f"&nbsp;&nbsp;`{m}`")


# ══════════════════════════════════════════════════════════════
#  TAB 1 — RESEARCH PAPER SEARCH
# ══════════════════════════════════════════════════════════════
if nav == "🔎 Search (Research Papers)":
    st.markdown('<div class="section-header">🔎 Research Paper Search Engine</div>', unsafe_allow_html=True)
    st.markdown("25 structured research papers (AI, Cybersecurity, Healthcare, Databases, SE, IR). Each document has title, abstract, methodology, results fields.")

    se = get_research_engine()

    col1, col2, col3, col4 = st.columns([4, 2, 1, 1])
    with col1:
        query = st.text_input("Search query", placeholder="machine learning intrusion detection",
                              label_visibility="collapsed")
    with col2:
        model = st.selectbox("Model", ["bm25","vsm","bim","boolean","overlap","nonoverlap","proximal","field_bm25"],
                             label_visibility="collapsed")
    with col3:
        top_k = st.number_input("Top K", min_value=1, max_value=25, value=5, label_visibility="collapsed")
    with col4:
        show_math = st.checkbox("Show math", value=False)

    cat_filter = st.selectbox("Category filter", ["(all)", "AI", "Cybersecurity", "Healthcare",
                                                    "Databases", "SoftwareEngineering", "IR"])
    mode_opt = st.radio("Boolean mode", ["any (OR)", "all (AND)", "not (NOT)"], horizontal=True)
    mode_map = {"any (OR)": "any", "all (AND)": "all", "not (NOT)": "not"}

    if query:
        t0 = time.perf_counter()
        results = se.search(
            query, model=model, top_k=top_k, show_math=show_math,
            mode=mode_map[mode_opt],
            category_filter=None if cat_filter == "(all)" else cat_filter,
        )
        took = round((time.perf_counter() - t0) * 1000, 1)

        hits = results.get("hits", [])
        st.markdown(f"**{len(hits)} results** &nbsp;·&nbsp; `{model}` &nbsp;·&nbsp; {took} ms",
                    unsafe_allow_html=True)

        if not hits:
            st.warning("No documents matched. Try different words or switch to OR mode.")
        else:
            top_score = hits[0]["score"] or 1
            for i, h in enumerate(hits, 1):
                render_result_card(h, i, top_score)
                if show_math and "explanation" in h:
                    with st.expander(f"📐 Math explanation for doc {h['id']}"):
                        st.code(h["explanation"], language="text")


# ══════════════════════════════════════════════════════════════
#  TAB 2 — FYP MOCK DATA SEARCH
# ══════════════════════════════════════════════════════════════
elif nav == "🐛 FYP Search (Mock Data)":
    st.markdown('<div class="section-header">🐛 FYP Mock Data Search — ShopEasy Bug Evidence</div>',
                unsafe_allow_html=True)
    st.markdown("""
    **1 492 real evidence documents** from the ShopEasy e-commerce platform:
    logs, commits, bug tickets, code chunks, schema changes.
    Ground-truth relevance judgments for **15 bug investigation queries** (BEIR format).
    """)

    idx, id_map = get_fyp_index()

    col1, col2, col3 = st.columns([5, 2, 1])
    with col1:
        q = st.text_input("Bug investigation query",
                          placeholder="checkout returns 500 error discount null",
                          key="fyp_q", label_visibility="collapsed")
    with col2:
        m = st.selectbox("Model", ALL_MODELS, key="fyp_m", label_visibility="collapsed")
    with col3:
        k = st.number_input("Top K", min_value=1, max_value=50, value=10,
                            key="fyp_k", label_visibility="collapsed")

    # preset queries
    queries = get_fyp_queries()
    qrels   = get_fyp_qrels()
    preset  = st.selectbox("Or pick a ground-truth query:",
                           ["(type your own)"] + [f"{q2['_id']}: {q2['text']}" for q2 in queries])
    if preset != "(type your own)":
        q = preset.split(": ", 1)[1]

    if q:
        t0   = time.perf_counter()
        if m == "boolean":
            raw_hits = boolean_search(q, idx, top_k=k)
        elif m == "bm25":
            raw_hits = bm25_search(q, idx, top_k=k)
        elif m == "vsm":
            raw_hits = vsm_search(q, idx, top_k=k)
        elif m == "bim":
            raw_hits = bim_search(q, idx, top_k=k)
        elif m == "overlap":
            raw_hits = overlapped_lists(q, idx)[:k]
        elif m == "nonoverlap":
            raw_hits = non_overlapped_lists(q, idx)[:k]
        elif m == "proximal":
            raw_hits = proximal_nodes(q, idx, top_k=k)
        else:
            raw_hits = field_bm25_search(q, idx, top_k=k)
        took = round((time.perf_counter() - t0) * 1000, 1)

        hits = translate_results(raw_hits, id_map)

        # find ground truth for this query if it matches a preset
        gt_relevant: set = set()
        matched_qid = None
        for q2 in queries:
            if q2["text"].strip().lower() == q.strip().lower():
                matched_qid = q2["_id"]
                gt_relevant = {cid for cid, sc in qrels.get(matched_qid, {}).items() if sc >= 1}
                break

        st.markdown(f"**{len(hits)} results** &nbsp;·&nbsp; `{m}` &nbsp;·&nbsp; {took} ms",
                    unsafe_allow_html=True)

        if gt_relevant:
            retrieved_ids = [h["corpus_id"] for h in hits]
            p_at_k = sum(1 for d in retrieved_ids if d in gt_relevant) / len(retrieved_ids)
            r_at_k = sum(1 for d in retrieved_ids if d in gt_relevant) / len(gt_relevant)
            mrr_val = next((1.0/i for i, d in enumerate(retrieved_ids, 1) if d in gt_relevant), 0.0)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(f"P@{k}", f"{p_at_k:.3f}")
            c2.metric(f"R@{k}", f"{r_at_k:.3f}")
            c3.metric("MRR",   f"{mrr_val:.3f}")
            c4.metric("Relevant docs", len(gt_relevant))

        if not hits:
            st.warning("No results. Try OR mode or different terms.")
        else:
            top_score = hits[0]["score"] or 1
            for i, h in enumerate(hits, 1):
                corpus_id = h.get("corpus_id", "")
                is_relevant = corpus_id in gt_relevant
                score = h.get("score", 0)
                pct   = int(100 * score / top_score) if top_score else 0
                bar   = f'<div class="score-bar-bg"><div class="score-bar-fill" style="width:{pct}%"></div></div>'
                rel_badge = '<span class="badge badge-best">✓ RELEVANT</span>' if is_relevant else ""
                doc_type = idx.docs.get(h["id"], {}).get("type", "")
                type_badge = _type_badge(doc_type) if doc_type else ""
                title = h.get("title") or corpus_id
                service = idx.docs.get(h["id"], {}).get("service", "")

                st.markdown(f"""
                <div class="result-card">
                  <span class="result-rank">#{i}</span>
                  <div class="result-title">{title or corpus_id}</div>
                  {bar}
                  <div class="result-snippet">{idx.docs.get(h['id'],{}).get('text','')[:160]}…</div>
                  <div class="result-meta">
                    {rel_badge}{type_badge}
                    <code>{corpus_id}</code>
                    {'&nbsp;·&nbsp;<code>' + service + '</code>' if service else ''}
                    &nbsp;·&nbsp; Score: <b style="color:#f5c518">{score}</b>
                    &nbsp;·&nbsp; Matched: <code>{', '.join(h.get('matched', []))}</code>
                  </div>
                </div>
                """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
#  TAB 3 — FYP MODEL COMPARISON
# ══════════════════════════════════════════════════════════════
elif nav == "📊 FYP Model Comparison":
    st.markdown('<div class="section-header">📊 FYP Model Comparison — 1 492 docs · 15 queries · BEIR qrels</div>',
                unsafe_allow_html=True)
    st.markdown("""
    All 8 IR models evaluated against the ShopEasy bug-investigation corpus.
    Ground-truth relevance from `qrels.tsv` (score 2 = highly relevant, 1 = relevant).
    **Metrics computed at k=10** (top 10 retrieved documents per query).
    """)

    col_run, col_info = st.columns([2, 5])
    with col_run:
        if st.button("▶ Run evaluation (all 8 models)", type="primary"):
            with st.spinner("Evaluating… ~30 seconds"):
                st.cache_data.clear()
                run_fyp_evaluation()
            st.success("Done! Results updated below.")

    # load saved results
    saved = load_saved_results()
    if saved is None:
        st.info("Click **Run evaluation** to compute metrics.")
        st.stop()

    rows     = saved["summary_rows"]
    by_model = saved["by_model"]
    k        = saved["k"]

    # ── best model banner ──────────────────────────────────────
    best_ndcg = saved["best_by_ndcg"]
    best_mrr  = saved["best_by_mrr"]
    best_map  = saved["best_by_map"]
    mm_best   = by_model[best_ndcg]["mean_metrics"]

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1a1500,#0d0d0d);
                border:1px solid #f5c518;border-radius:10px;padding:16px 20px;margin-bottom:18px">
      <span style="font-size:1.5rem">🏆</span>
      <span style="color:#f5c518;font-size:1.2rem;font-weight:700;margin-left:10px">
        Best model: {best_ndcg.upper()}
      </span>
      <span style="color:#aaa;font-size:0.88rem;margin-left:14px">
        nDCG@{k}={mm_best.get(f'nDCG@{k}',0):.4f} &nbsp;|&nbsp;
        MRR={mm_best.get('MRR',0):.4f} &nbsp;|&nbsp;
        MAP={mm_best.get('MAP',0):.4f} &nbsp;|&nbsp;
        P@{k}={mm_best.get(f'P@{k}',0):.4f}
      </span>
    </div>
    """, unsafe_allow_html=True)

    # ── summary metrics table ──────────────────────────────────
    st.markdown('<div class="sub-header">Mean metrics across all 15 queries</div>', unsafe_allow_html=True)

    metric_keys = [f"P@{k}", f"R@{k}", f"F1@{k}", "MRR", "MAP", f"nDCG@{k}"]
    df_rows = []
    for r in rows:
        row = {"Model": r["model"]}
        for mk in metric_keys:
            row[mk] = r.get(mk, 0.0)
        row["Time(ms)"] = r.get("took_ms", 0)
        df_rows.append(row)
    df = pd.DataFrame(df_rows).sort_values(f"nDCG@{k}", ascending=False).reset_index(drop=True)

    # colour-code the cells
    def highlight_row(row):
        styles = []
        for col in row.index:
            if col == "Model":
                if row["Model"] == best_ndcg:
                    styles.append("background-color: #1a1500; color: #f5c518; font-weight: bold")
                else:
                    styles.append("")
            elif col == "Time(ms)":
                styles.append("color: #888")
            else:
                val = row[col]
                col_vals = df[col].values
                best_v = float(col_vals.max())
                worst_v = float(col_vals.min())
                ratio = (val - worst_v) / (best_v - worst_v + 1e-9)
                if ratio >= 0.85:
                    styles.append("color: #69ff47; font-weight: bold")
                elif ratio >= 0.50:
                    styles.append("color: #ffd740")
                else:
                    styles.append("color: #ff5252")
        return styles

    styled = (df.style
              .apply(highlight_row, axis=1)
              .format({mk: "{:.4f}" for mk in metric_keys})
              .format({"Time(ms)": "{:.1f}"}))
    st.dataframe(styled, use_container_width=True, height=320)

    # ── metric bar charts ──────────────────────────────────────
    st.markdown('<div class="sub-header">Visual comparison</div>', unsafe_allow_html=True)
    chart_metric = st.selectbox("Chart metric", metric_keys, index=metric_keys.index(f"nDCG@{k}"))
    chart_df = df[["Model", chart_metric]].sort_values(chart_metric, ascending=True)
    st.bar_chart(chart_df.set_index("Model"), color="#f5c518", use_container_width=True)

    # ── per-query breakdown ─────────────────────────────────────
    st.markdown('<div class="sub-header">Per-query breakdown</div>', unsafe_allow_html=True)
    sel_model = st.selectbox("Select model for per-query detail", ALL_MODELS,
                             index=ALL_MODELS.index(best_ndcg) if best_ndcg in ALL_MODELS else 0)
    if sel_model in by_model:
        pq = by_model[sel_model]["per_query"]
        pq_df = pd.DataFrame([
            {k2: v for k2, v in q.items()
             if k2 not in ("retrieved",)}
            for q in pq
        ])
        # reorder columns
        first_cols = ["query_id", "query_text", "num_relevant"]
        other_cols = [c for c in pq_df.columns if c not in first_cols]
        pq_df = pq_df[first_cols + other_cols]
        st.dataframe(pq_df, use_container_width=True, height=400)

    # ── model explanation table ─────────────────────────────────
    st.markdown('<div class="sub-header">Why BM25 wins on this corpus</div>', unsafe_allow_html=True)
    explanations = {
        "bm25":       ("✅ Best overall", "Rare error tokens (NoneType, timeout, 500) get high IDF. TF saturation and length normalisation prevent noisy long logs from dominating."),
        "vsm":        ("🥈 Second",       "Same IDF weighting as BM25 but no TF saturation — a log repeating 'error' 20 times scores 20× higher, which is too much."),
        "nonoverlap": ("🥉 Third",        "Finds docs where ANY query term appears in ANY field. Good recall, but equal term weights mean common words hurt ranking."),
        "proximal":   ("4th",             "Rewards terms in adjacent fields (title+text). Useful for structured docs; less effective on flat log lines."),
        "bim":        ("5th",             "IDF-like weights, no term frequency. Misses the signal that a term appearing 3× in a log is stronger evidence than once."),
        "field_bm25": ("6th",             "BM25 per field with title boost. Correct for structured papers; our FYP corpus has mostly flat text fields with no meaningful title."),
        "overlap":    ("7th",             "All terms must co-occur in the SAME field. Most bugs span multiple log lines → very low recall (12.7% precision only)."),
        "boolean":    ("❌ Worst",        "Default OR returns 0 documents because the porter stemmer maps 'NoneType' → 'nonetyp' which isn't in the index. No ranking at all."),
    }
    for model_name, (rank_str, reason) in explanations.items():
        mm = by_model.get(model_name, {}).get("mean_metrics", {})
        ndcg_val = mm.get(f"nDCG@{k}", 0)
        st.markdown(f"""
        <div style="background:#111;border:1px solid #2a2a2a;border-radius:6px;
                    padding:10px 14px;margin-bottom:6px;{'border-left:3px solid #f5c518' if model_name==best_ndcg else ''}">
          <b style="color:#f5c518">{model_name.upper()}</b>
          <span style="color:#888;font-size:0.82rem;margin-left:8px">{rank_str}</span>
          <span style="color:#ffd740;font-size:0.88rem;margin-left:8px">nDCG@{k}={ndcg_val:.4f}</span>
          <div style="color:#ccc;font-size:0.84rem;margin-top:4px">{reason}</div>
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
#  TAB 4 — PIPELINE TRACE
# ══════════════════════════════════════════════════════════════
elif nav == "🔬 Pipeline Trace":
    st.markdown('<div class="section-header">🔬 Query Pipeline Trace</div>', unsafe_allow_html=True)
    st.markdown("Watch what happens to a query at every stage: tokenisation → stop-word removal → stemming → index lookup → scoring → ranking.")

    trace_q = st.text_input("Enter any query", value="checkout returns 500 error discount null")
    if trace_q:
        stages = analyze_pipeline(trace_q)
        steps = [
            ("1. Raw input",             trace_q),
            ("2. Tokenized",             " · ".join(stages["tokens"])),
            ("3. Stop-words removed",    " · ".join(stages["no_stop"]) or "(all removed)"),
            ("4. Porter-stemmed",        " · ".join(stages["stems"])  or "(empty)"),
        ]
        for name, val in steps:
            st.markdown(f"""
            <div class="pipeline-step">
              <div class="step-name">{name}</div>
              <div class="step-val"><code>{val}</code></div>
            </div>""", unsafe_allow_html=True)

        se = get_research_engine()
        idx_r = se.index
        st.markdown('<div class="pipeline-step"><div class="step-name">5. Index lookup</div></div>',
                    unsafe_allow_html=True)
        for stem in stages["stems"]:
            df_val = idx_r.df(stem)
            docs   = sorted(idx_r.postings.get(stem, {}).keys())[:8]
            st.markdown(f"&nbsp;&nbsp;&nbsp;`{stem}` → **df={df_val}** docs {docs}{'…' if df_val>8 else ''}")

        st.markdown("""
        <div class="pipeline-step">
          <div class="step-name">6. Scoring (BM25)</div>
          <div class="step-val">score(D,Q) = Σ IDF(t) × tf(t,D)×(k1+1) / (tf(t,D) + k1×(1-b+b×|D|/avgdl))</div>
        </div>
        <div class="pipeline-step">
          <div class="step-name">7. Ranking + top-k</div>
          <div class="step-val">Sort by score descending, return top k results with source locators</div>
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
#  TAB 5 — SLIDE VERIFICATION
# ══════════════════════════════════════════════════════════════
elif nav == "📐 Slide Verification":
    st.markdown('<div class="section-header">📐 Slide Example Verification</div>', unsafe_allow_html=True)

    st.markdown("### Cosine Similarity (binary weights)")
    slide = verify_slide_example()
    c1, c2, c3 = st.columns(3)
    c1.metric("D1 cosine (expected 0.816)", f"{slide['cosine_D1']:.4f}", delta="✓" if abs(slide['cosine_D1']-0.816)<0.01 else "✗")
    c2.metric("D2 cosine (expected 0.408)", f"{slide['cosine_D2']:.4f}", delta="✓" if abs(slide['cosine_D2']-0.408)<0.01 else "✗")
    c3.metric("D3 cosine (expected 0.000)", f"{slide['cosine_D3']:.4f}", delta="✓" if abs(slide['cosine_D3']-0.000)<0.01 else "✗")

    st.markdown("### Sigmoid (Probability of Relevance)")
    sig = verify_sigmoid_example()
    c1, c2, c3 = st.columns(3)
    c1.metric("sigmoid(3.5) expected 0.9707", f"{sig['sigmoid'][0]:.4f}")
    c2.metric("sigmoid(2.0) expected 0.8808", f"{sig['sigmoid'][1]:.4f}")
    c3.metric("sigmoid(4.8) expected 0.9918", f"{sig['sigmoid'][2]:.4f}")

    st.markdown("### BM25 Step-by-Step")
    se = get_research_engine()
    bm25_q = st.text_input("Query for BM25 walkthrough", value="best treatment for diabetes")
    doc_id  = st.number_input("Document ID", min_value=1, max_value=25, value=11)
    if bm25_q:
        from text_processing import preprocess
        terms = preprocess(bm25_q)
        st.code(bm25_explain(terms, doc_id, se.index), language="text")

    st.markdown("### VSM Explanation")
    vsm_q = st.text_input("Query for VSM walkthrough", value="information retrieval search ranking")
    if vsm_q:
        st.code(vsm_explain(vsm_q, se.index), language="text")


# ══════════════════════════════════════════════════════════════
#  TAB 6 — CLASSIFICATION & CLUSTERING
# ══════════════════════════════════════════════════════════════
elif nav == "🏷️ Classification & Clustering":
    st.markdown('<div class="section-header">🏷️ Classification & Clustering</div>', unsafe_allow_html=True)
    se = get_research_engine()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Naive Bayes Classification**")
        if st.button("Run Naive Bayes"):
            with st.spinner("Training…"):
                clf_result = classify_documents(se.index)
            st.metric("Accuracy", f"{clf_result['accuracy']:.2%}")
            st.code(clf_result["report"], language="text")

    with col2:
        st.markdown("**K-Means Clustering**")
        n_clusters = st.slider("Number of clusters", 2, 8, 5)
        if st.button("Run K-Means"):
            with st.spinner("Clustering…"):
                clust_result = cluster_documents(se.index, n_clusters=n_clusters)
            for i, cluster in enumerate(clust_result["clusters"]):
                st.markdown(f"**Cluster {i+1}** — top terms: `{', '.join(cluster['top_terms'])}`")
                for d in cluster["docs"][:3]:
                    st.markdown(f"&nbsp;&nbsp;&nbsp;• {d}")


# ══════════════════════════════════════════════════════════════
#  TAB 7 — FILTERING DEMO
# ══════════════════════════════════════════════════════════════
elif nav == "📬 Filtering Demo":
    st.markdown('<div class="section-header">📬 Ad-hoc vs Filtering Demo</div>', unsafe_allow_html=True)
    st.markdown("""
    **Ad-hoc** retrieval answers a one-time query.
    **Filtering** maintains a long-term user profile and automatically
    pushes relevant new documents to the user — like a personalised alert system.
    """)
    se = get_research_engine()

    st.markdown("### User Profile")
    kw   = st.text_input("Interest keywords", value="machine learning intrusion detection cybersecurity")
    cats = st.multiselect("Preferred categories", ["AI", "Cybersecurity", "Healthcare", "Databases", "SoftwareEngineering", "IR"],
                          default=["AI", "Cybersecurity"])
    thresh = st.slider("Match threshold", 0.0, 1.0, 0.3, 0.05)

    if st.button("Run filtering demo"):
        profile = UserProfile(name="Demo User", interest_keywords=kw.split(),
                              category_preferences=cats)
        matched = []
        for doc_id, doc in se.index.docs.items():
            score = profile.match_score(doc, se.index)
            if score >= thresh:
                matched.append({"id": doc_id, "title": doc.get("title",""),
                                 "category": doc.get("category",""), "score": score})
        matched.sort(key=lambda x: -x["score"])
        st.markdown(f"**{len(matched)} documents match** your profile (threshold ≥ {thresh})")
        for h in matched[:10]:
            st.markdown(f"- `[{h['id']}]` **{h['title']}** — *{h['category']}* — score `{h['score']}`")
