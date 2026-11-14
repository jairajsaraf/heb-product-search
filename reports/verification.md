# Verification report

Status: **Phases 6a and 6b.** Sections 1 to 5 (6a) were produced without opening the 58 locked queries. Section 6 (6b) records the single `--final` run and what followed it. The service was deployed to Cloud Run by the owner and audited with Lighthouse (6.6).

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

## 6. Phase 6b (2026-11-14)

Base: `origin/main` at `794dd19` (PR #8 merged), branch `claude/phase6b-final-b295de`. Every command below was run from the repo root with `.venv\Scripts\python.exe` and `HF_HUB_OFFLINE=1`.

### 6.1 Settled before the run

Decisions are the owner's, recorded in [holdout_prereg.md](holdout_prereg.md) and committed as `9d1d826` **before** the locked set was opened.

| Item | Outcome |
|---|---|
| Headline config (reviewer item 3) | Pinned to what the API ships: MiniLM, BM25 weight 0.10. `--final` scores the constants imported from `tamu25/api/search.py` and exits before reading locked rows if all-dev tuning or the model revision disagrees. |
| Once-only guard (item 3) | `--final` refuses to start if `reports/holdout_final.json` exists; the file is written with exclusive create. Test `test_final_refuses_if_output_exists`. |
| Image ships locked labels (item 2) | Kept, accepted. The repo is public (confirmed, `gh repo view --json visibility`), so the labels are already downloadable. |
| `split:"held_out"` (item 5) | Kept, accepted (spec M8; membership is public in `data/split_v1.json`). |
| Filter test on real data (item 4) | Added: `test_locked_labels_never_served_on_real_data`. 58 locked queries return `held_out` and no label; 230 dev queries return labels. |

Checks before the run (confirmed, exit codes read from the shell, except where marked):

| Command | Exit | Result |
|---|---|---|
| `python -m pytest tests -q` (before any change) | 0 (inferred: the output was piped through `tail`, so the code was not captured) | 18 passed |
| `python -m pytest tests -q` (after guard, pin, tests) | 0 | **20 passed** |
| `python scripts/eval_cv.py` | 0 | `reports/cv_baseline.json` byte-identical (`git diff --quiet`) |
| Rehearsal of the `--final` branch, dev fold 0 posing as locked, output to a scratch file | 0 | BM25 composite 0.5741 = the fold-0 mean in `cv_baseline.json`. No locked row read. |
| Same rehearsal again, scratch output present | 1 | "exists; the locked set is scored once, refusing to run again" |

### 6.2 The locked-set run

Command: `python scripts/eval_cv.py --final`. **Exit code 0.** Run once, from commit `9d1d826` with a clean tree (`meta.git_head`, `meta.git_dirty: false` in the output). Output: [holdout_final.json](holdout_final.json). 58 locked queries, depth 30. All numbers below are confirmed from that file.

The tuned hybrid is both the tuned baseline and the final system (no Phase 3 change was kept), so "tuned baseline vs final system" is 0 by construction. The comparison is against BM25.

| System | Official composite | Judged-only | Unjudged in top 10 | nDCG@10 | AP@20 | P@10 | R@30 |
|---|---|---|---|---|---|---|---|
| BM25 | 0.6273 | 0.7248 | 0.245 | 0.7189 | 0.4714 | 0.6000 | 0.7208 |
| **Tuned hybrid (final system)** | **0.6998** | 0.7311 | 0.069 | 0.7590 | 0.5662 | 0.6707 | 0.8063 |

Paired bootstrap, tuned hybrid minus BM25, 10,000 resamples, seed 20261113, 95% percentile interval, 58 queries:

| Metric | Δ [95% CI] | Resamples above 0 |
|---|---|---|
| **Official composite (headline)** | **+0.0725 [+0.0404, +0.1068]** | 100% |
| Judged-only composite | +0.0063 [−0.0143, +0.0271] | 72.6% |

Reading it:

- **The official gain holds on the locked set** and agrees with the dev estimate from section 3 (+0.0717 [+0.0552, +0.0886]). The locked interval is wider because it rests on 58 queries, not 230.
- **The judged-only gain does not.** Its interval includes 0. On dev the judged-only means were 0.7046 (BM25) and 0.7227 (tuned); that difference was never bootstrapped, so whether it was significant on dev is unknown.
- Inferred: much of the official gain comes from the hybrid putting labelled products where BM25 puts unlabelled ones (unjudged in top 10: 24.5% vs 6.9%), since the official metric scores every unlabelled product as irrelevant. Whether those unlabelled BM25 results are actually irrelevant cannot be told from these labels.
- **Reviewer item 1.** The BM25 locked mean was derivable beforehand as (288 × 0.6089 − 230 × 0.6042) / 58 ≈ 0.6275; the run gives 0.6273. The fixed hybrids (≈ 0.6937 MiniLM 0.3/0.7, ≈ 0.6886 mpnet 0.2/0.8) are derivable the same way and were not scored. The tuned hybrid's locked mean and the per-query differences were not derivable, so the bootstrap is the headline, not either mean.
- Config scored (`config_scored`): MiniLM at revision `1110a243…`, BM25 weight 0.10, dev composite 0.6788; all-dev tuning independently picks the same config.
- Nothing was re-tuned or changed after the run. No per-query locked value was printed, stored or inspected; the output file holds aggregates only.

### 6.3 README headline numbers (M9)

Written from `holdout_final.json`, each linked to its file: the Key Features bullet, the Performance Metrics block and table (with the derivability statement and the judged-only caveat), the two "Performance" lines under Algorithm Details, and the benchmark table (now "Locked-Set Performance"). A grep of the README for "pending Phase 6" and "TBD" returns nothing. The relative gain +11.6% is my arithmetic (0.6998 / 0.6273), not a field in the file.

### 6.4 Latency (M13)

Command: `python scripts/build_index.py` (exit 0, `artifacts/index.npz` 3287 × 384), then `python scripts/latency.py` (**exit 0**). Output: [latency.json](latency.json).

Per query through `Searcher.search(q, 30)`, the function behind `GET /search` (no HTTP layer). 191 unlabelled test queries, one untimed warm-up pass over all of them, then one timed pass with the two systems interleaved. Device `cpu`, **24 torch threads** (torch default; inferred to be what the served app uses, since nothing in `tamu25/api` sets a thread count), Intel64 Family 6 Model 183, 32 logical CPUs, Windows 11, torch 2.15.0+cpu.

| System | p50 | p95 | mean | max |
|---|---|---|---|---|
| Final system (hybrid) | 22.2 ms | 29.3 ms | 22.7 ms | 61.9 ms |
| BM25 only | 7.0 ms | 10.4 ms | 7.1 ms | 13.7 ms |

- One run. Phase 3 saw the same setting drift 1.75× between sessions on this laptop, so compare the two rows with each other, not with other runs. Phase 3's 26.7 / 33.6 ms was `HybridRanker.rank` at 12 threads on 46 dev queries: a different path and thread count.
- This says nothing about Cloud Run, which will have 1 to 2 vCPUs. Unknown until deployed.
- **Served path = scored path (confirmed).** The same script compares `Searcher.search` top 30 with the harness ranking at BM25 weight 0.10 on all 230 dev queries: identical order on 230 of 230 (`served_path_check`). So the config scored in 6.2 is the one the API returns, checked on dev queries; the locked queries were not put through this check.
- Doc read: `docs.pytorch.org/docs/2.15/generated/torch.set_num_threads.html` ("must be called before running eager, JIT or autograd code"), which is why the script does not change the thread count mid-process.

### 6.5 Human kit (M12)

Command: `python scripts/human_kit.py` (**exit 0**; a second run reproduces both files byte for byte). Outputs: [human_kit.md](human_kit.md) and [human_kit_key.json](human_kit_key.json).

- 10 queries drawn with `random.Random(20261113)` from the 191 test queries sorted by id; top 10 per side; each system is side A for 5 queries, in an order shuffled with `random.Random(20261114)`; the key is in the separate file.
- A first version drew side A with one coin flip per query. Its key order was printed into the build session's log during a check, so that draw was discarded and replaced by the balanced shuffle. The queries and both lists are unchanged. The new order was checked by count only (5 and 5) and never printed.
- Sides are **BM25 vs the final system** (owner's decision), because the spec's two sides are the same system. 0 of the 10 queries have identical lists.
- Rubric: "which list would you buy from?", answer `A`, `B` or `same`. **Not run:** the owner runs it. Do not open the key first.
- Titles are HTML-unescaped for display only (adjacent issue 4 in `adjacent_issues.md` is unchanged in the data).

### 6.6 Cloud Run deploy and Lighthouse

**Deployed by the owner on 2026-11-14**, following a step-by-step guide; the build session ran none of the deploy commands. Lighthouse was run afterwards with the owner's approval (end of this section).

Service: `heb-search`, project `product-search-514708`, region `us-central1`, URL `https://heb-search-246501698420.us-central1.run.app/`.

Image: the 6a image `heb-search:6a`, pushed as `us-central1-docker.pkg.dev/product-search-514708/heb-search/heb-search:6b`. No file the image copies has changed since it was built (confirmed, `git diff 6f96a35` over the Dockerfile's inputs is empty), so it serves the same code and config that 6.2 scored.

Settings (confirmed, `gcloud run services describe` and `get-iam-policy`): revision `heb-search-00001-v9n`, 1 CPU, 2 GiB memory, container port 8080, concurrency 80, startup CPU boost on, ingress `all`, `roles/run.invoker` granted to `allUsers` (public, unauthenticated).

**Instance cap: 1 for this revision, not for the service.** The revision annotation `autoscaling.knative.dev/maxScale` is `1` (from `--max-instances 1`). The service-level annotation `run.googleapis.com/maxScale` is `20`. The effective limit is the lesser of the two (confirmed, docs.cloud.google.com/run/docs/configuring/max-instances), so the service runs at most one instance today. The cap belongs to this revision, though; a later deploy without the flag would not carry it. The guide used the revision-level flag; the service-level flag is `--max`. **Since fixed by the owner:** a later `describe` shows `run.googleapis.com/maxScale` is `1` (confirmed), so the cap is now service-wide as the spec requires.

Smoke test against the public URL (confirmed by curl, 2026-11-14):

| Check | Result |
|---|---|
| `GET /` | 200 `text/html`, the built `index.html` |
| `GET /search?q=gluten free pasta&k=3` | 200, 3 results, `mode: hybrid`, `split: null`, bm25, semantic and final scores present |
| `GET /search?q=x&k=999` | 422 (cap enforced) |
| `GET /healthz` | **404**, served by Google's front end, not by the app |
| 5 warm `GET /search?q=organic almond milk&k=30` | server-side `latency_ms` 23.2 to 36.4; client round trip 0.09 to 0.11 s |

- `/healthz` is unreachable on Cloud Run. The known-issues page says "You can't use the following URL paths: … Some paths ending with `z`" (docs.cloud.google.com/run/docs/known-issues). Inferred: `/healthz` is one of them, since the 404 body is Google's and the same image answers `/healthz` locally (section 5). The app is healthy; only the route is shadowed. Not fixed.
- The five timings are a smoke observation on a warm instance, not a benchmark: no committed script, no saved output. Cold-start time was not measured. Memory in use on Cloud Run was not measured.
- Docs read for the guide: docs.cloud.google.com/run/docs/deploying, docs.cloud.google.com/sdk/gcloud/reference/run/deploy, docs.cloud.google.com/artifact-registry/docs/docker/store-docker-container-images, and local `gcloud --help` for each command.

**Lighthouse** (approved by the owner as "Run with npx"). Command, from the repo root:

`npx --yes lighthouse https://heb-search-246501698420.us-central1.run.app/ --output json --output-path=./reports/lighthouse.json --chrome-flags="--headless" --no-enable-error-reporting --quiet`

**Exit code 0.** Output: [lighthouse.json](lighthouse.json). Lighthouse 13.6.0, headless Chrome on the build laptop, default settings: mobile form factor, simulated throttling (150 ms RTT, 1.6 Mbps, 4× CPU slowdown). No run warnings, no runtime error. All values confirmed from the file.

| Category | Score |
|---|---|
| Performance | 100 |
| Accessibility | 100 |
| Best practices | 96 |
| SEO | 90 |
| Agentic browsing | 100 |

| Metric | Value |
|---|---|
| First Contentful Paint | 1.2 s |
| Largest Contentful Paint | 1.2 s |
| Total Blocking Time | 0 ms |
| Cumulative Layout Shift | 0 |
| Speed Index | 1.2 s |
| Root document response | 40 ms |
| Total transfer size | 379 KiB |

- The two failed audits: `errors-in-console` (the browser's request for `/favicon.ico` gets a 404) and `meta-description` (the page has none). Neither was fixed.
- **Scope:** one run, of the landing page only, before any search. The results list and the Debug score rows were not audited, so the accessibility score does not cover them (the Phase 5b wiring and contrast checks do).
- The instance was warm, so this is not a cold-start measurement. A single run varies; no repeat was made.
- "Agentic browsing" is a category in this Lighthouse version; which of its audits applied to this page was not checked.
- Doc read: the Lighthouse readme, "Using the Node CLI" (github.com/GoogleChrome/lighthouse/blob/main/readme.md), for `--output`, `--output-path`, `--chrome-flags`, `--quiet` and `--no-enable-error-reporting`.

**Health route fix and redeploy (2026-11-14, after PR #9; requested by the owner).** The route was renamed from `/healthz` to `/health` in `tamu25/api/app.py`, `tests/test_api.py` and the dev proxy in `frontend/vite.config.ts`, because Cloud Run reserves some paths ending in `z`. The ranking code, model and weights are untouched, so 6.2 still describes what is served. The smoke test and Lighthouse run above were made against the previous revision.

| Step | Command | Exit | Result |
|---|---|---|---|
| Tests | `python -m pytest tests -q` | 0 | 20 passed |
| Build | `docker build -t heb-search:6c .` | 0 | 2.25 GB; the frontend stage (`npm ci`, `tsc -b`, `vite build`) passed with the proxy change |
| Local smoke | `docker run -p 8081:8080 heb-search:6c`, curl | n/a | `/health` 200 `{"status":"ok","mode":"hybrid"}`; `/healthz` 404 from the app; `/search` 200; `k=999` 422; `/` 200 |
| Push | `docker push us-central1-docker.pkg.dev/product-search-514708/heb-search/heb-search:6c` | 0 | digest `sha256:5655ed95…` |
| Deploy | `gcloud run deploy heb-search --image …:6c --region us-central1 --project product-search-514708 --allow-unauthenticated --max-instances 1 --max 1 --memory 2Gi --cpu 1 --port 8080` | 0 | revision `heb-search-00002-c7j`, 100% of traffic |

Live check after the deploy (confirmed by curl and `gcloud run services describe`): `GET /health` 200 `{"status":"ok","mode":"hybrid"}`; `GET /search?q=gluten free pasta&k=3` 200; `k=999` 422; `GET /` 200. Settings unchanged: 1 CPU, 2 GiB, revision and service maximum both 1 instance, public access. `/healthz` still returns Google's 404, as expected. The frontend unit tests were not run locally (no `node_modules` in this worktree); the image build compiled the frontend.

## 7. Open items

Items 1 to 5 were the pre-run list from 6a; all are settled.

1. ~~Headline config~~: pinned to the API config, pre-registered (6.1).
2. ~~Refuse-if-exists guard~~: added and tested (6.1).
3. ~~Image labels and `held_out`~~: both kept and accepted by the owner (6.1).
4. ~~Python test for the locked-label filter~~: added (6.1).
5. ~~Derivability statement and bootstrap headline~~: in 6.2 and the README.

Still open:

6. Cloud Run cold-start time and memory in use are unmeasured (6.6). Lighthouse covered the landing page only.
7. **Human kit not yet run** by the owner (6.5).
8. A result title contains a literal `&nbsp;` in the UI ("White&nbsp;Cheddar Mac & Cheese"). Adjacent; not fixed.
9. `make evaluate` default exits 0 with composite 0.0 on 191 unlabelled queries (section 2). Adjacent; not fixed.

Found in 6b, listed, not fixed:

10. `final_config.json` `provenance.final_system` still says "Locked-set headline comes in Phase 6" and "BM25 weight 0.10-0.15 per fold". It was not in the 6b task list.
11. The README still describes the system as mpnet at 20/80 in the overview, architecture diagram, technology stack, Algorithm Details, Optimization Process and API examples. The final system is MiniLM at BM25 weight 0.10. Only the headline numbers were in scope.
12. The README's four "Runtime Performance" bullets and the Scalability list remain unsourced (already in `adjacent_issues.md`); a measured table now sits above them.
13. `reports/adjacent_issues.md` item 6 ("`--final` has never been run or tested") is now out of date.
14. The judged-only difference on dev (tuned vs BM25) was never bootstrapped, so the dev and locked judged-only results cannot be compared interval to interval.
15. The human kit's first side-A draw was discarded because its key reached the build log (6.5). The kit is blind to the owner, not to the session that built it.
16. `scripts/eval_cv.py` imports `tamu25.api.search` for the pin, so the harness now depends on the API module's constants.
17. ~~`GET /healthz` returns Google's 404 on Cloud Run~~: renamed to `/health` and redeployed (6.6). Section 5 still shows `/healthz`, which was the route at the time.
18. ~~The one-instance cap was revision-level only~~: the owner set the service-level maximum to 1 (6.6).
19. The frontend has no favicon (`/favicon.ico` is a 404, logged as a console error) and no meta description (6.6, Lighthouse).
