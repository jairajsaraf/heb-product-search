# Verification report

Status: **Phase 6a only.** Sections 1 to 5 were produced without opening the 58 locked queries. Section 6 (locked-set run, README numbers, human kit, deploy) is **pending Phase 6b**. Nothing here was run with `--final`.

Base: `main` at `6f96a35` (Phase 5b merged). Claims are marked **confirmed** (source named), **inferred**, or **unknown**.

## 1. Test suite

Command: `.venv\Scripts\python.exe -m pytest tests -q` from the repo root.
Result (confirmed): exit code 0, **18 passed** in 10.77 s. Same count before and after the 6a work (6a changes no code).

## 2. Makefile targets in a throwaway Linux container (M3)

`python:3.12-slim` (pulled with approval), repo mounted read-only at `/repo`, `apt-get install make` (GNU Make 4.4.1), `pip install fire google-cloud-storage` (fire 0.7.1, google-cloud-storage 3.17.1). Outputs went to `/tmp/out` inside the container.

Command pattern: `make RUN= TAMU25="python -m tamu25.cli.main" OUT_DIR=/tmp/out <target>`

| Target | Exit | Result (confirmed from container output) |
|---|---|---|
| `make validate` (default `TEAM=team-git-em`) | 0 | "Validation passed", 191 queries checked, avg depth 30 |
| `make evaluate` (default team) | 0 | **composite 0.0 over 191 queries**; see caveat |
| `make evaluate TEAM=team_alpha` | 0 | composite 0.0 over 4 queries (a 4-query, 40-row placeholder file) |

Caveat (confirmed): the default `evaluate` exits 0 but is not a meaningful score. The default submission covers the 191 *test* queries, which have no labels, and the target scores them against the train labels file. Meaningful local scoring needs a submission over the train queries. This matches the spec note "cannot be scored locally" and the adjacent issue on `evaluate.py:52`. Not changed here.

The `RUN=` override works as designed in Phase 4. The `poetry run` default was not exercised (no poetry).

## 3. Cross-validation, before and after (230 dev queries, out-of-fold)

Source: `reports/cv_baseline.json` and `reports/cv_results.json`/`.md`. Nothing re-tuned or recomputed. Official composite = 0.30 nDCG@10 + 0.30 AP@20 + 0.25 R@30 + 0.15 P@10, depth 30.

**Original BM25 (before) vs tuned hybrid (after).** Paired bootstrap, 10,000 resamples, seed 20261113, 95% percentile interval.

| System | Official composite | Judged-only | Unjudged in top 10 |
|---|---|---|---|
| BM25 alone (before) | 0.6042 | 0.7046 | 0.289 |
| Fixed MiniLM 0.3/0.7 | 0.6624 | 0.7247 | 0.164 |
| Fixed mpnet 0.2/0.8 | 0.6653 | 0.7335 | 0.174 |
| **Tuned hybrid, out-of-fold (after, final system)** | **0.6759** | 0.7227 | 0.108 |

Tuned hybrid minus BM25: **+0.0717, 95% CI [+0.0552, +0.0886]**, 230 queries, 100% of resamples above 0 (`cv_baseline.json: bootstrap_tuned_hybrid_vs_bm25`). Every fold chose MiniLM; BM25 weight 0.15 (folds 0, 2) or 0.10 (folds 1, 3, 4).

**Phase 3 candidates against the tuned baseline** (`cv_results.json: comparisons`):

| Change | Official Δ [95% CI] | Judged-only Δ [95% CI] | Decision |
|---|---|---|---|
| RRF | −0.0039 [−0.0102, +0.0024] | −0.0034 [−0.0093, +0.0026] | fail |
| Cross-encoder rerank | −0.0150 [−0.0307, +0.0006] | +0.0080 [−0.0057, +0.0222] | inconclusive, not kept |

The final system is the tuned baseline. No ranking change passed the gate. Per-system intervals on the mean are not stored in the committed files; only paired differences are.

## 4. Fresh-reviewer leakage pass

Reviewer: `ecc:mle-reviewer`, run before any locked data was opened. It got the repo path and the task (audit for leakage of locked queries/labels into selection, tuning, analysis or reporting, and within CV), not my conclusions, and was told not to print locked ids, texts or labels. It was read-only and ran nothing with `--final`.

Verbatim report:

> LEAKAGE AUDIT. Nothing was run. This was a read-only review, and `--final` was not invoked. No locked id, text or label is quoted below.
>
> VERDICT: no blocking leakage into anything selected, tuned or analysed. No code path that I read touches locked labels before `--final`. There are 3 should-fix items and 5 notes.
>
> FINDINGS
>
> 1. [should-fix] Pooled-288 Phase 0 numbers let a reader back out the locked-set mean for three systems.
>    - Evidence: `reports/baseline_repro.json` gives depth-30 composites over all 288 queries for BM25, MiniLM 0.3/0.7 and mpnet 0.2/0.8. `reports/cv_baseline.json:systems` gives the same three systems over the 230 dev queries.
>    - Locked-set mean = (288*pooled - 230*dev) / 58. At 4-decimal rounding this is good to roughly 0.001, because `eval_cv` is tested equal to `evaluate_submission`.
>    - It did not influence any selection: `reports/cv_baseline.json` shows every fold chose MiniLM, which is the opposite of the pooled-288 mpnet edge. It does mean the Phase 6 comparators (BM25 and the fixed hybrids) are not unseen.
>    - The tuned hybrid on locked queries is not derivable.
>    - Confirmed by reading: both report files and the arithmetic. Inferred: that the final report will quote these baselines.
>    - Fix: in the Phase 6 write-up, state that BM25 and the fixed hybrids were already known pooled. Make the tuned-vs-BM25 bootstrap, which uses per-query locked values, the headline.
>
> 2. [should-fix] The shipped image contains all 288 labels plus the split file.
>    - Evidence: `Dockerfile` copies `data/labels_synth_train.json` and `data/split_v1.json`.
>    - The API itself is clean. `tamu25/api/search.py:30-38,50` builds the label map only from non-locked ids, so locked labels never enter memory or a response.
>    - Confirmed by reading: the Dockerfile and the filter. The risk is only that the label file is extractable from the image, and the filter is the sole barrier.
>    - Fix: ship a dev-only labels file, or ship none. The API needs the labels only for the dev label display.
>
> 3. [should-fix] `--final` has no once-only guard, and the config it scores may differ from the shipped one.
>    - Evidence: `scripts/eval_cv.py:284-296` overwrites `reports/holdout_final.json` on every run and has no refusal if the file exists. The file is not gitignored.
>    - The `--final` path re-tunes on all 230 dev queries (`eval_cv.py:287`, any model and weight in the grid). The API hard-codes MiniLM at BM25 weight 0.10 (`tamu25/api/search.py:15`). The README says "0.10-0.15".
>    - Neither of the two systems that `--final` scores (the all-dev-tuned hybrid and BM25) is guaranteed to equal what is deployed. All-dev tuning could pick 0.15 or mpnet.
>    - Confirmed by reading: the code. Inferred: that the all-dev tuning could pick a different config.
>    - Fix: pre-register which config is the headline before running `--final`. Either pin it, or deploy whatever `--final` selects. Add a refuse-if-exists guard on the output file.
>
> 4. [note] `tests/test_api.py` never exercises the locked-label filter.
>    - Evidence: the Searcher is built without `data_dir`, so `load_dev_labels` and the `split="held_out"` path are untested in Python. The UI test (`frontend/src/App.test.tsx:89`) covers only the frontend side.
>    - Fix: add a test using the real `data/` files showing a locked query text returns `label=None` and `split="held_out"`.
>
> 5. [note] The API exposes a membership oracle.
>    - Evidence: `search.py:72` returns `split:"held_out"` for exact (normalised) locked query texts. It returns rankings but no labels for them.
>    - A user could probe whether a guessed text is locked, and could eyeball ranking quality on locked queries.
>    - Fix: return `null` for locked texts, or accept the risk.
>
> 6. [note] Phase 0 was run on all 288 queries before the split existed. The disclosure is honest.
>    - Evidence: `reports/error_analysis.md:9` discloses the 5-query score-spread check, and 2 of those 5 are locked. Scores only, no labels.
>    - `reports/baseline_repro.json` lines 94, 103, 141 and 150 list those locked ids with spreads.
>    - Other id hits in `reports/error_analysis.md` (lines 150, 213, 235, 236, 488, 530) are false positives, so no locked data is there. Tokens like "s27" there are semantic ranks that collide with query-id syntax. Confirmed: 0 overlap between product ids and locked ids.
>
> 7. [note] `final_config.json` and the fixed comparator weights (0.3 for MiniLM, 0.2 for mpnet) came from the original repo, which was apparently tuned on all 288 training queries.
>    - Evidence: `final_config.json` provenance line "on all 288 train queries".
>    - This was not used for selection, since `eval_cv.GRID` is a full 0..1 grid at 0.05 steps. The mpnet 0.2/0.8 comparator will be optimistic on locked queries.
>    - Inferred, not confirmed: how the weights were originally derived.
>
> 8. [note] One locked query has a near-duplicate dev query. It was found at token-set Jaccard ≥ 0.8, a threshold I chose. That is 1 of 58, so the effect is minimal.
>    - Exact duplicate texts across the split: 0, within locked: 0, within dev: 0.
>
> CHECKED AND CLEAN (confirmed by reading unless marked)
> - `locked_ids` raises `PermissionError` without `--final` (`eval_cv.py:52-55`). `load_data` filters queries and labels to dev ids unless `--final`.
> - `scripts/cv_results.py:99` and `scripts/error_analysis.py:78` call `load_data(final=False)`. A grep across all Python files and the Makefile finds locked ids read only in `eval_cv.py`, in `make_split`, and in `tamu25/api/search.py`.
> - The Makefile and `generate_final_submission.py` use the test queries, which are unlabeled, or the `final_config.json` values.
> - Split: a seeded shuffle of sorted ids, and the balance check uses dev labels only. Locked queries are checked only on query-token length, which uses query text and no labels. The split uses no models.
> - Committed outputs: `reports/cv_baseline.json`, `reports/cv_results.json` and `reports/error_analysis.json` each have 230 per-query rows with 0 locked ids. No locked query text appears anywhere in `reports/`, `frontend/src`, the README or the tests. `tests/data` has 0 locked ids. `.cache` is gitignored.
> - Score cache (`eval_cv.py:161-175`): the key hashes the query ids and texts, the catalog, the rankers, the model revision and the library versions, and each cache file name carries its own tag. A dev cache cannot contain locked rows, and a locked cache hits only for the locked list.
> - Tuning is nested correctly. `evals` is computed for all dev queries, but `tune()` averages only the 4 training folds (`eval_cv.py:253-255`), and the held-out fold is scored with the chosen config. Fold structure follows the split file. The `cv_results.py` `oof()` and RRF k-grid selection do the same, with the grid fixed beforehand, and the baseline reproduction is asserted equal.
> - No cross-query learning: scoring and max-normalisation are per query, and BM25 is built on the catalog only. The nDCG ideal is built from the submitted list (`tamu25/metrics.py:19`). That is a metric quirk, not leakage.
> - Error-analysis bucket rules are query-text-only or label-count rules on dev queries. The worst-20 list is dev only.
> - The keep rules in `scripts/cv_results.py` run only on dev out-of-fold results. The final system "baseline" was chosen on dev alone: RRF and rerank failed against it. The choice of MiniLM over mpnet came from the 5 per-fold results, not from Phase 0.
> - Frontend: `frontend/src/App.tsx:44` shows labels only when `split === "dev"`, and a held-out response never shows a label (the test at line 89 covers that). Fixtures contain no real ids.
> - Determinism: seeded split, seeded bootstrap (10,000 resamples), stable argsort in the hybrid. The BM25 `argsort` is unstable, but it is identical to the shipped ranker.
>
> NOT CHECKED
> - Whether the `.cache` directory on disk or `artifacts/` exist locally. Neither is committed.
> - Notebooks. There are none in the repo.
> - `semantic_ranker.py` and `baseline_ranker.py` internals beyond a grep. They contain no label or split reads.

**Disposition (mine, not the reviewer's).** No finding was fixed in 6a, since fixing needs code changes outside the named scope. Items 2 and 3 must be settled **before** the `--final` run; they are listed in section 7. Note the item-3 hazard in particular: `--final` overwrites `holdout_final.json` with no guard, so a second run would silently replace the first.

## 5. Container (built with approval)

`docker build -t heb-search:6a .` of the multi-stage `Dockerfile`: exit 0, 3 min 49 s wall (confirmed, build log). Both previously unverified items hold: the `node:24-slim` tag exists and the `npm ci` + `npm run build` stage succeeds. `build_index.py` downloaded MiniLM from Hugging Face inside the build (approved) and wrote `artifacts/index.npz` (3287 x 384).

**Smoke test** (`docker run -d -p 8080:8080 heb-search:6a`, confirmed by curl):

| Check | Result |
|---|---|
| `GET /healthz` | 200, `{"status":"ok","mode":"hybrid"}` |
| `GET /search?q=gluten free pasta&k=3` | 200, 3 results with bm25, semantic and final scores, `split: null`, 51 ms |
| `GET /search?q=x&k=999` | 422 (cap enforced) |
| `GET /` | 200 `text/html`, the built `index.html` |

The image sets `HF_HUB_OFFLINE=1`, and the container started and served without error (inferred that it needs no network at runtime; no network-isolated run was done).

**Screenshot:** [frontend_screenshot.jpg](frontend_screenshot.jpg). Built-in browser pane at `http://localhost:8080/`, query "gluten free pasta", Debug on, showing the per-component score row. It is an ad-hoc non-dataset query.

**Size and memory** (measured before any Cloud Run setting is chosen):

| Measure | Value |
|---|---|
| Image size | **2.25 GB** on disk (`docker images`); 2,247,710,101 bytes (`docker image inspect`) |
| Index layer | 98.9 MB (model cache + `index.npz`) |
| Memory, idle (`docker stats`) | 417 MiB |
| Memory, after 30 `/search` calls | 418 MiB |
| uvicorn process `VmRSS` | 583 MB (includes shared mapped pages; larger than the cgroup figure) |

Inferred: the working set is flat across queries, so about 0.6 GB is the number to size against; a 1 GiB Cloud Run limit is plausible but untested. Cold-start time was **not measured**. The host has 15.5 GiB and many cores, so this says nothing about Cloud Run CPU limits. The final choice waits for 6b.

## 6. Pending Phase 6b (not done, placeholders)

- [ ] **Locked-set run:** one `--final` run, tuned baseline vs final system on the 58 locked queries, with interval. Output `reports/holdout_final.json`. *Pending.*
- [ ] **README headline numbers**, each linking its output file (M9). *Pending.*
- [ ] **Human kit:** `reports/human_kit.md`, `reports/human_kit_key.json`. *Pending.*
- [ ] **Latency (M13)** on the 191 unlabelled test queries, warm, CPU. *Pending; Phase 3 latency used 46 dev queries.*
- [ ] **Cloud Run deploy and Lighthouse run:** needs approval by name, a project id and a region. Service capped at one instance. *Pending.*

## 7. Open items before 6b (from the reviewer and from this phase; none fixed)

1. Decide and record which config is the headline (reviewer item 3). The `--final` path re-tunes on all 230 dev queries; the API is pinned to MiniLM at BM25 0.10.
2. Add a refuse-if-exists guard on `reports/holdout_final.json` (item 3).
3. Decide whether the image should ship the locked labels (item 2) and whether `split:"held_out"` should be exposed (item 5).
4. Add a Python test for the locked-label filter on real `data/` files (item 4).
5. In the 6b write-up, state that BM25 and fixed-hybrid locked means are derivable from Phase 0 pooled numbers (item 1) and make the tuned-vs-BM25 bootstrap the headline.
6. Seen in the UI, not in the reviewer report: a result title contains a literal `&nbsp;` ("White&nbsp;Cheddar Mac & Cheese"), so product titles carry unescaped HTML entities. Adjacent; not fixed.
7. `make evaluate` default exits 0 with composite 0.0 on 191 unlabelled queries (section 2). Adjacent; not fixed.
