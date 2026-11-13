# Phase 0: baseline reproduction

Source: `reports/baseline_repro.json`, produced by `scripts/repro_baseline.py`. All 288 train queries, scored with `tamu25.evaluate.evaluate_submission` unchanged, rankers unchanged. Aggregates only; no per-query inspection.

Env: Python 3.12.10, torch 2.15.0+cpu, sentence-transformers 6.3.0, transformers 5.23.0, numpy 2.5.4, rank-bm25 0.2.2, CPU, 24 torch threads.
Model revisions: all-MiniLM-L6-v2 `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`; all-mpnet-base-v2 `e8c3b32edf5434bc2275fc9bab85f82640a19130`.

## Composite (nDCG@10 in brackets)

| System | Depth 30 | Depth 50 |
|--------|----------|----------|
| BM25 | 0.6089 (0.7217) | **0.6016** (0.6975) |
| Hybrid MiniLM 0.3/0.7 | 0.6687 (0.7607) | 0.6621 (0.7386) |
| Hybrid mpnet 0.2/0.8 | 0.6700 (0.7636) | **0.6638** (0.7430) |

## Findings

- **Both README/config numbers reproduce exactly, at depth 50:** BM25 = 0.6016, mpnet 0.2/0.8 = 0.6638. Their source was the original 50-result scripts.
- **Depth changes the score.** AP@20, P@10, R@30 are identical at 30 and 50; only nDCG@10 moves, because its ideal is built from the submitted list (`tamu25/metrics.py:19`). BM25 gains +0.0073 composite from depth 50 to 30 with no ranking change.
- **Relative improvement is +10.3% (depth 50: 0.6638/0.6016), not +25.67%.** At depth 30: mpnet +10.0%, MiniLM +9.8%.
- **mpnet vs MiniLM: +0.0013 (depth 30), +0.0017 (depth 50).** Not tested for significance (Phase 1).
- **Scale mismatch confirmed** (5 queries, std over all 3,287 products): BM25-normalised std 0.11-0.15; `(cos+1)/2` std 0.05-0.08 (range ~0.41-0.88). With weights 0.2/0.8, effective spread is about 0.03 (BM25) vs 0.05 (semantic) per query, roughly 1.8:1, not the stated 4:1.
- Existing 8 tests pass on the new stack.

## Not done / caveats

- Depth-30 numbers are the Phase 1+ baseline; depth-50 numbers exist to tie back to the README.
- `poetry.lock` untouched (no poetry here). `requirements.txt` pinned to the installed versions, including non-ML packages; dev/doc dependencies were not reinstalled and keep their old pins.
- Nothing committed.
