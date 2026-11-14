# Pre-registration for the locked-set run (Phase 6b)

Written 2026-11-14, **before** `scripts/eval_cv.py --final` has ever been run on the 58 locked queries. This note is committed first; `reports/holdout_final.json` records the commit it ran from (`meta.git_head`, `meta.git_dirty`). Claims are marked **confirmed** (source named), **inferred**, or **unknown**.

## What is scored

One run of `scripts/eval_cv.py --final`, on the 58 locked queries in `data/split_v1.json`, depth 30:

| System | Config |
|---|---|
| BM25 | `BM25Ranker`, unchanged |
| Tuned hybrid | linear BM25 + `all-MiniLM-L6-v2`, BM25 weight **0.10**, semantic weight 0.90 |

- The tuned hybrid is **both** the tuned baseline and the final system. No Phase 3 change passed the keep rule (`reports/cv_results.md`), so the spec's "tuned baseline vs final system" is the same ranking twice and its difference is 0 by construction. The comparison that carries information is tuned hybrid vs BM25.
- **Headline:** the paired bootstrap of tuned hybrid minus BM25 on the official composite (10,000 resamples, seed 20261113, 95% percentile interval), from per-query locked values. The same bootstrap on the judged-only composite, and the unjudged-in-top-10 rate, are reported beside it (spec Q4).
- Nothing else is scored on the locked set: not mpnet, not the fixed 0.3/0.7 or 0.2/0.8 hybrids, not RRF, not the reranker. The output file holds aggregates only, no per-query locked rows.

## Decisions (owner, 2026-11-14)

1. **Headline config is pinned to what the API ships.** `--final` scores the model and weight imported from `tamu25/api/search.py` (`MODEL_NAME`, `BM25_WEIGHT`, `MODEL_REVISION`). It does not re-tune. It still computes the all-230-dev tuning pick, records it, and **exits before reading any locked row** if that pick or the cached model revision differs from the pin.
   - Dev-only evidence (confirmed by the rehearsal below, which printed it; no locked data): tuning on all 230 dev queries picks MiniLM at BM25 weight 0.10, mean dev composite 0.6788. A scratch run showed 0.15 at 0.6787. So "pin" and "deploy what `--final` selects" are the same config.
2. **Once-only guard.** `--final` refuses to start if `reports/holdout_final.json` exists, and writes the file with exclusive create. Test: `tests/test_eval_cv.py::test_final_refuses_if_output_exists`.
3. **Image contents (reviewer item 2): kept as is, accepted.** The image ships all 288 labels and the split file. The GitHub repo is public (confirmed, `gh repo view --json visibility`), so the locked labels are already downloadable from the repo; removing them from the image would protect nothing. The API filter stays the barrier and is now tested on the real files: `tests/test_api.py::test_locked_labels_never_served_on_real_data`.
4. **`split:"held_out"` (reviewer item 5): kept, accepted.** It is spec decision M8, and membership is public through `data/split_v1.json`.
5. **Human kit sides:** BM25 vs the final system, because the spec's two sides are the same system.

## What was already known about the locked set before this run

Reviewer item 1 (`reports/verification.md` section 4): three locked-set means can be backed out of committed Phase 0 and Phase 1 numbers as (288 × pooled − 230 × dev) / 58. From `reports/baseline_repro.json` (depth 30, 288 queries) and `reports/cv_baseline.json` (230 dev queries), each rounded to 4 decimals, so the result is good to about ±0.0005 (inferred from the rounding):

| System | Pooled 288 | Dev 230 | Derived locked mean |
|---|---|---|---|
| BM25 | 0.6089 | 0.6042 | ≈ 0.6275 |
| MiniLM 0.3/0.7 | 0.6687 | 0.6624 | ≈ 0.6937 |
| mpnet 0.2/0.8 | 0.6700 | 0.6653 | ≈ 0.6886 |

So the BM25 locked mean is **not unseen**; the run should reproduce about 0.6275. The tuned hybrid's locked mean and every per-query locked value are not derivable from anything committed. No selection used the derived numbers: every CV fold chose MiniLM on dev data alone.

Also known: Phase 0 printed score spreads (no labels) for 5 queries, 2 of them locked (`reports/error_analysis.md:9`).

## Rules after the run

- The result is reported whatever it shows. Nothing is re-tuned, and no config, test or note is changed in response to it.
- No per-query locked result is inspected.
- README headline numbers are copied from `reports/holdout_final.json` and link to it.

## Rehearsal (dev data only)

The `--final` branch had never executed (`reports/adjacent_issues.md`). Before this note it was run end to end with dev fold 0 standing in for the locked list and the output redirected to a scratch file (scratch script, not committed): exit code 0, and its BM25 composite for that fold equals the fold-0 mean in `reports/cv_baseline.json` (0.5741). A second rehearsal against the existing scratch output exited 1 with the refusal message. The real locked ids were not read.
