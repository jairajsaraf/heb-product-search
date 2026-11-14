# Phase 3: flagged ranking changes, measured on the 230 dev queries

Source: `scripts/cv_results.py` → `reports/cv_results.json`. Versions, model revisions, devices, grids and the sha256 of `cv_baseline.json` and `split_v1.json` are in its `meta`. The locked 58 queries are never loaded. All numbers below are **confirmed** from that file unless marked otherwise.

## Result

**Neither change passes the keep rule. The final system stays the Phase 1 tuned baseline**: linear hybrid, MiniLM, BM25 weight 0.10–0.15 chosen per fold. Phases 4–6 proceed with it, as the spec prescribes.

| System | Official composite | Judged-only | Unjudged in top 10 | nDCG@10 | AP@20 | P@10 | R@30 |
|---|---|---|---|---|---|---|---|
| Tuned baseline | **0.6759** | 0.7227 | 0.108 | 0.7544 | 0.5392 | 0.6165 | 0.7813 |
| RRF | 0.6720 | 0.7193 | 0.120 | 0.7535 | 0.5355 | 0.6174 | 0.7706 |
| Cross-encoder rerank | 0.6609 | **0.7308** | 0.180 | 0.7514 | 0.5215 | 0.5783 | 0.7691 |

Paired bootstrap against the baseline (10,000 resamples, seed 20261113, 95% percentile interval):

| Change | Official Δ [95% CI] | Judged-only Δ [95% CI] | Decision |
|---|---|---|---|
| RRF | −0.0039 [−0.0102, +0.0024] | −0.0034 [−0.0093, +0.0026] | **fail** |
| Cross-encoder rerank | −0.0150 [−0.0307, +0.0006] | +0.0080 [−0.0057, +0.0222] | **inconclusive**: fails the gate while judged-only rises; not kept |

The combination was not run, because the spec tests it only if both changes pass alone.

## What happened

- **RRF** (tested at the owner's request; Phase 2 had not recommended it):
  - Every fold chose MiniLM, with k = 40 (3 folds) or 60 (2 folds).
  - It is slightly worse on both official and judged-only, and neither interval excludes 0.
  - This matches the Phase 2 count: only 44 missing items were reachable through the BM25 side.
- **Cross-encoder rerank:**
  - Official composite drops (better on 95 queries, worse on 123, unchanged on 12).
  - Judged-only rises, and the unjudged-in-top-10 rate goes from 0.108 to 0.180. The reranker moves unlabelled products into the top 10, and the official metric scores every one of them as irrelevant.
  - Inferred: from these labels it cannot be told whether the reranker ranks better. Its judged-only gain is also not significant.
  - Phase 2's label-hole finding predicted this risk, and the spec's "inconclusive" rule exists for exactly this case.
  - Inferred: the model is trained on MS MARCO web passages, not grocery products. A domain-tuned reranker might behave differently, but that is a new candidate, not a retune of this one.
- **No variant was tried after seeing these results** (score interpolation, a different depth or product text). Choosing one now would be tuning on all 230 dev queries by eye.

## Latency (confirmed; CPU)

End to end through `HybridRanker.rank(top_k=30)`, warm, 12 torch threads, the 4 configurations interleaved per query, on 46 fixed dev queries (every 5th; ids in the JSON).
- **Machine:** Intel Family 6 Model 183 laptop CPU, Windows 11, torch 2.15.0+cpu.
- **Configurations:** the latency runs use the most-chosen fold config, MiniLM with BM25 weight 0.10 for the baseline and k = 40 for RRF.

| Configuration | p50 | p95 |
|---|---|---|
| Baseline | 26.7 ms | 33.6 ms |
| RRF | 20.5 ms | 26.8 ms |
| Rerank | 2,303 ms | 2,882 ms |
| RRF + rerank (timed for completeness; not evaluated) | 2,266 ms | 2,889 ms |

Timings on this laptop drift between sessions. The same setting measured 1.75× apart in two earlier scratch runs. Compare rows within this table, not with other runs.

## Model added in this phase

`cross-encoder/ms-marco-MiniLM-L6-v2`, revision `233902d25c440f23af6f7d6e94d2946bac0bee0a`, 91 MB safetensors, Apache-2.0. Downloaded with the owner's approval. It runs on CPU and is loaded only when `HybridRanker(..., reranker_model=...)` is used. Docs read before coding against it: the sentence-transformers CrossEncoder reference (sbert.net/docs/package_reference/cross_encoder/cross_encoder.html), for the constructor (`revision`, `device`) and `predict` (`batch_size` default 32, returns a numpy array).

## Code

- **`semantic_ranker.py`:** two flags, both off by default.
  - `rank(fusion='rrf', rrf_k=...)` and `rank(rerank=True, rerank_depth=...)`. The reranker needs `HybridRanker(..., reranker_model=..., reranker_revision=...)`.
  - The original weighted sum is unchanged; it moved into `_linear`.
  - The shared functions `tie_ranks`, `rrf_fuse`, `rerank_text`, `rerank_scores` and `rerank_order` are used by both the ranker and the harness, so the evaluated code is the shipped code.
- **`tests/test_ranker_flags.py`:** one test per flag, with stub encoder and cross-encoder (no model, no network). The RRF test includes a tie.

## Checks

- **Default path unchanged:** editing `semantic_ranker.py` invalidated the score cache. After the rebuild, `scripts/eval_cv.py` regenerated `reports/cv_baseline.json` byte-identically (`git diff --quiet` clean).
- **Baseline reproduced:** the harness asserts the baseline's 230 per-query composites equal Phase 1.
- **Shipped path matches the harness:** on 10 dev queries, `HybridRanker.rank` top 30 equals the harness ranking for baseline, rerank and RRF. That's 18 rankings, compared where the query's fold config matches the latency config.
- **Tests:** `python -m pytest tests -q` gives 14 passed.

## Rules fixed before the first run

- **RRF:** k ∈ {1, 5, 10, 20, 40, 60, 100}, model ∈ {MiniLM, mpnet}, tuned per fold on the 4 training folds. Ranks are tie-aware, so equal scores share the best rank.
- **Reranker:** pure reorder of each query's baseline top 50 (its fold's config), no new tunable. Product text is `title. Brand: brand. Category: category_path. description`, with one `predict` call per query.
- **Keep rule:** as in the spec.
- **Scoring threads:** torch default (24), matching the Phase 1 caches. Latency only runs at 12 threads.
