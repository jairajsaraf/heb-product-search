# TAMU-25 H-E-B Product Ranking System

Product search for the TAMU-25 H-E-B Datathon: a linear hybrid of BM25 keyword scores and `all-MiniLM-L6-v2` sentence-embedding similarity, served by a FastAPI service with a React frontend in one container.

The final system uses BM25 weight 0.10 and semantic weight 0.90 over 3,287 products. The constants live in [`tamu25/api/search.py`](tamu25/api/search.py). [`reports/cv_results.md`](reports/cv_results.md) documents the choice, and [`reports/holdout_prereg.md`](reports/holdout_prereg.md) fixed it before the locked set was scored. Nothing is trained or fine-tuned; both components are used as published.

On 58 held-out queries, scored once, the hybrid reaches an official composite of **0.6998** against **0.6273** for BM25 alone: **+0.0725, 95% CI [+0.0404, +0.1068]** ([`reports/holdout_final.json`](reports/holdout_final.json)).

Every number in this README links to the file it comes from. Where a claim has no source file, it says so.

---

## Results

> **Final system.** A linear BM25 + MiniLM hybrid with BM25 weight 0.10, chosen by 5-fold cross-validation on 230 dev queries (0.10 in 3 of 5 folds, 0.15 in the other 2). RRF fusion and cross-encoder reranking were tested and did not pass the keep rule, so neither is used. See [`reports/cv_results.md`](reports/cv_results.md) and [`reports/cv_baseline.json`](reports/cv_baseline.json).

> **Headline (locked set).** 58 queries were set aside before any tuning or error analysis and scored exactly once, with the config fixed in advance ([`reports/holdout_prereg.md`](reports/holdout_prereg.md)). The headline is the paired difference between the final system (BM25 + MiniLM, BM25 weight 0.10, the config the API serves) and BM25 alone: **+0.0725 official composite, 95% CI [+0.0404, +0.1068]** (paired bootstrap over the 58 queries, 10,000 resamples; every resample above 0). Source: [`reports/holdout_final.json`](reports/holdout_final.json), written by `scripts/eval_cv.py --final`.

| Metric (58 locked queries, depth 30) | Baseline (Keyword Only) | Our System (Hybrid) | Difference [95% CI] | Source |
|--------|------------------------|---------------------|-------------|--------|
| Official composite | 0.6273 | 0.6998 | +0.0725 [+0.0404, +0.1068] | [`holdout_final.json`](reports/holdout_final.json) |
| Judged-only composite | 0.7248 | 0.7311 | +0.0063 [−0.0143, +0.0271] | [`holdout_final.json`](reports/holdout_final.json) |
| Unjudged products in top 10 | 24.5% | 6.9% | | [`holdout_final.json`](reports/holdout_final.json) |

How to read this:

- **The official gain is real on unseen queries** and matches the cross-validated estimate on the 230 dev queries: 0.6042 → 0.6759, +0.0717 [+0.0552, +0.0886] ([`reports/cv_baseline.json`](reports/cv_baseline.json)). As a ratio it is 0.6998 / 0.6273 = +11.6%.
- **The judged-only gain is not distinguishable from zero.** The official metric counts every unlabelled product as irrelevant, and BM25 puts far more unlabelled products in its top 10. Much of the official gain therefore comes from the hybrid returning products that have labels. Whether BM25's unlabelled results were actually bad is unknown from this data.
- **Not every locked number was unseen.** The locked-set means of BM25 (and of the fixed MiniLM 0.3/0.7 and mpnet 0.2/0.8 hybrids, which were not scored here) could already be derived from the Phase 0 numbers over all 288 queries and the dev numbers: (288 × pooled − 230 × dev) / 58 gives ≈ 0.6275 for BM25, and the run measured 0.6273. The hybrid's locked score and the per-query differences behind the interval were not derivable, which is why the paired bootstrap is the headline rather than either mean.
- The earlier 66.38% / 60.16% / +25.67% figures are not used. 0.6016 (BM25) and 0.6638 (mpnet 0.2/0.8) do reproduce at depth 50 on all 288 training queries, but the relative gain is +10.3%, not +25.67% ([`reports/baseline_repro.md`](reports/baseline_repro.md)).

All locked-set metrics ([`reports/holdout_final.json`](reports/holdout_final.json)):

| System | Approach | Composite | nDCG@10 | MAP@20 | P@10 | R@30 |
|------|----------|-----------|---------|--------|------|------|
| Final system | BM25 + MiniLM, BM25 weight 0.10 | 0.6998 | 0.7590 | 0.5662 | 0.6707 | 0.8063 |
| Baseline | BM25 only | 0.6273 | 0.7189 | 0.4714 | 0.6000 | 0.7208 |

### What was tried and not kept

All on the 230 dev queries, out of fold ([`reports/cv_results.md`](reports/cv_results.md)):

| System | Official composite | Judged-only | Decision |
|---|---|---|---|
| Tuned hybrid (final) | 0.6759 | 0.7227 | kept |
| RRF fusion | 0.6720 | 0.7193 | fails the keep rule (official Δ −0.0039 [−0.0102, +0.0024]) |
| Cross-encoder rerank | 0.6609 | 0.7308 | inconclusive: official Δ −0.0150 [−0.0307, +0.0006], judged-only Δ +0.0080 [−0.0057, +0.0222]; not kept |

The cross-encoder moves unlabelled products into the top 10 (0.108 → 0.180 of the top 10), and the official metric scores each as irrelevant. From these labels it cannot be told whether it ranks better. mpnet at 0.2/0.8, the earlier config, scores 0.6653 on the same dev queries against 0.6759 for the final system ([`reports/cv_baseline.json`](reports/cv_baseline.json)); it was not scored on the locked set.

### Latency

Measured ([`reports/latency.json`](reports/latency.json), `scripts/latency.py`): per query through `Searcher.search`, the function behind `GET /search` (no HTTP layer), on the 191 test queries, warm, CPU, 24 torch threads, Intel Family 6 Model 183 laptop (32 logical CPUs), Windows 11:

| System | p50 | p95 |
|---|---|---|
| Final system (hybrid) | 22.2 ms | 29.3 ms |
| BM25 only | 7.0 ms | 10.4 ms |

This says nothing about Cloud Run, which has fewer CPUs. Cloud Run cold-start time and memory in use are not measured ([`reports/verification.md`](reports/verification.md) section 7). The container image size and local memory use are in section 5 of the same file.

### Known limits

- Query and product text are synthetic; labels exist only for the 288 training queries, so the 191 test queries cannot be scored locally.
- The hybrid's gain is measured with an official metric that penalises unlabelled products. See "How to read this" above.
- A blind human comparison kit exists ([`reports/human_kit.md`](reports/human_kit.md)); it has not been run.
- Open and adjacent issues: [`reports/adjacent_issues.md`](reports/adjacent_issues.md) and section 7 of [`reports/verification.md`](reports/verification.md).

---

## How it works

```
 query ──► BM25 (title ×3, brand ×2, categories ×2, description, ingredients)
      │         score ÷ max score
      │
      └──► all-MiniLM-L6-v2 embedding, cosine against precomputed product embeddings
                (cos + 1) / 2

 final = 0.10 × bm25 + 0.90 × semantic  ──►  top 30 products
```

- **BM25** ([`baseline_ranker.py`](baseline_ranker.py), `BM25Ranker`, Okapi BM25 from `rank-bm25`). The indexed text repeats the title three times and brand and category levels twice, then appends description and ingredients. The `safety_warning` field is not indexed.
- **Semantic** ([`semantic_ranker.py`](semantic_ranker.py), `HybridRanker`). Products and queries are encoded with `all-MiniLM-L6-v2` (384 dimensions) and compared by cosine similarity.
- **Fusion** ([`tamu25/api/search.py`](tamu25/api/search.py), `Searcher`). BM25 is divided by its maximum, semantic is `(cos + 1) / 2`, and the two are summed with weights 0.10 and 0.90. The API reuses the same BM25 class and the same scoring as `HybridRanker._linear`; the encoder revision is pinned in `search.py`.
- **Served path equals scored path.** `Searcher.search` returned the same top 30 as the harness ranking for all 230 dev queries ([`reports/latency.json`](reports/latency.json), `served_path_check`).

### Metrics

The official composite ([`tamu25/evaluate.py`](tamu25/evaluate.py), [`tamu25/metrics.py`](tamu25/metrics.py)):

```
composite = 0.30 × nDCG@10 + 0.30 × AP@20 + 0.25 × R@30 + 0.15 × P@10
```

Relevance is graded 0 to 3. Products without a label for the query count as relevance 0. "Judged-only" removes unlabelled products from the depth-30 list before scoring, without refilling.

### Evaluation harness

[`scripts/eval_cv.py`](scripts/eval_cv.py) is the only place the final system is scored:

- **Split.** [`data/split_v1.json`](data/split_v1.json) puts 58 of the 288 training queries in a locked set and the other 230 in five dev folds (seed 20261113).
- **Tuning.** Per fold, the model (MiniLM or mpnet) and BM25 weight (0 to 1 in steps of 0.05) are chosen on the four other folds and scored on the held-out fold. Output: [`reports/cv_baseline.json`](reports/cv_baseline.json).
- **Locked set.** `--final` scores BM25 and the config pinned in `search.py` on the 58 locked queries, and refuses to run if `reports/holdout_final.json` already exists. It has been run once; do not run it again.

---

## Data

All under `data/`:

| File | Content |
|---|---|
| `products.json` | 3,287 products: `product_id`, `title`, `description`, `brand` (some values are descriptors such as "Fresh", not brands), `category_path` (levels joined by ` -> `), `safety_warning`, `ingredients` |
| `queries_synth_train.json` | 288 queries with labels |
| `queries_synth_test.json` | 191 queries, no labels |
| `labels_synth_train.json` | 10,974 judgments (`query_id`, `product_id`, `relevance` 0 to 3) |
| `split_v1.json` | the 230 dev / 58 locked split |

Relevance scale: 3 exactly what the customer wants, 2 good alternative, 1 related but not ideal, 0 not relevant.

---

## Repository layout

```
tamu25/
  api/app.py           FastAPI app: GET /search, GET /health, serves the built frontend
  api/search.py        Searcher: hybrid scoring, per-component scores, dev-label lookup
  cli/main.py          `tamu25` CLI: validate, evaluate, version, info
  evaluate.py, metrics.py, validate.py
baseline_ranker.py     BM25Ranker
semantic_ranker.py     HybridRanker (linear fusion; RRF and cross-encoder flags, off by default)
frontend/              React + Vite app (src/, vitest tests, contrast check)
scripts/               eval_cv.py, build_index.py, latency.py, cv_results.py, error_analysis.py,
                       repro_baseline.py, human_kit.py, aggregate_leaderboard.py
reports/               every measured result and the file that produced it
data/                  see above
teams/                 submissions; team-git-em is the real one (191 test queries), the rest are examples
tests/                 pytest suite
Dockerfile             two-stage build: frontend, then API image with the model and index baked in
Makefile               validate / evaluate / lint / unittest targets
final_config.json      legacy config, see "Configuration"
```

---

## Setup

Python 3.11+ (`pyproject.toml`; the container uses 3.12).

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` pins `torch==2.15.0` with a note to install the CPU build from `https://download.pytorch.org/whl/cpu`. Poetry (`pyproject.toml`, `poetry.lock`) is also supported, but `poetry.lock` is stale ([`reports/adjacent_issues.md`](reports/adjacent_issues.md)); the `Makefile` runs commands through `poetry run` by default.

The first run downloads `all-MiniLM-L6-v2` from Hugging Face. sentence-transformers contacts the Hub even for cached models unless you set `HF_HUB_OFFLINE=1`.

### Tests

```bash
python -m pytest tests -q
```

### Search service

```bash
python scripts/build_index.py                     # writes artifacts/index.npz (3287 products x 384)
uvicorn tamu25.api.app:app --port 8000
```

Environment variables: `HEB_DATA_DIR` (default `data`), `HEB_INDEX` (default `artifacts/index.npz`), `HEB_FRONTEND_DIR` (default `frontend/dist`). The frontend is served only if `frontend/dist/index.html` exists; the API starts without it.

```bash
curl "http://localhost:8000/health"
# {"status":"ok","mode":"hybrid"}

curl "http://localhost:8000/search?q=gluten%20free%20pasta&k=3"
```

`GET /search` takes `q` (1 to 200 characters) and `k` (1 to 30, default 30); anything outside that range returns 422. The response has `query`, `split`, `mode`, `latency_ms` and `results`. Each result has `rank`, `product_id`, `title`, `brand`, `score`, `bm25_score`, `semantic_score`, `rerank_score` (always null; the reranker is not used) and `label`.

The API never serves locked labels. `split` is `dev` for the 230 dev queries, and `label` then holds the judged relevance (0 if unjudged). `split` is `held_out` for the 58 locked queries and null for any other query. `label` is null unless `split` is `dev`. Test: `tests/test_api.py::test_locked_labels_never_served_on_real_data`.

### Frontend

```bash
cd frontend
npm ci
npm run dev      # Vite dev server; proxies /search and /health to http://127.0.0.1:8000
npm test         # vitest
npm run build    # tsc -b && vite build, into frontend/dist
```

The page shows the ranked list, the dev label where one exists, and (Debug switch, on by default) the final, BM25 and semantic scores per result. It registers a read-only `search_products` tool through `@ui-sdk/react` agent support ([`frontend/src/agent.ts`](frontend/src/agent.ts)). A screenshot is in [`reports/frontend_screenshot.jpg`](reports/frontend_screenshot.jpg), and a Lighthouse run of the landing page in [`reports/lighthouse.json`](reports/lighthouse.json).

### Container

```bash
docker build -t heb-search .
docker run -p 8080:8080 heb-search
```

The build downloads MiniLM and computes the index inside the image, sets `HF_HUB_OFFLINE=1`, and serves the API and the built frontend on one origin. The server listens on `$PORT`, which Cloud Run sets, and on 8080 if unset. Build, smoke-test and deploy records: [`reports/verification.md`](reports/verification.md) sections 5 and 6.6. The image also contains all 288 labels and `split_v1.json`; the repository is public, so the owner accepted this ([`reports/holdout_prereg.md`](reports/holdout_prereg.md), decision 3).

Deployed on Google Cloud Run (`us-central1`, 1 CPU, 2 GiB, at most one instance, public and unauthenticated; [`reports/verification.md`](reports/verification.md) 6.6). The health route is `/health` because `/healthz` returned Google's own 404 on Cloud Run; the cause is inferred from Cloud Run's known-issues page, which reserves some paths ending in `z`.

---

## Command-line tools

The `tamu25` CLI (Fire) validates and scores submissions. Entry point: `tamu25.cli.main:main`. It imports `google.cloud.storage` at load, so that package must be installed.

```bash
python -m tamu25.cli.main validate \
  --submission teams/team-git-em/submission.json \
  --products data/products.json \
  --queries_synth data/queries_synth_test.json \
  --team team-git-em \
  --out validation_report.json

python -m tamu25.cli.main evaluate \
  --submission <submission.json> \
  --labels_synth data/labels_synth_train.json \
  --team <team> \
  --out score_report.json
```

Optional: `--queries_real` for `validate`, `--labels_real` for `evaluate`. `validate` checks, among other things, that each query has at least 30 results ([`tamu25/validate.py`](tamu25/validate.py)). `team-git-em` covers the 191 test queries, which have no labels here, so it validates but cannot be scored locally.

Makefile targets (default prefix `poetry run`; override with `make RUN= TAMU25="python -m tamu25.cli.main" ...`):

```bash
make validate TEAM=team-git-em   # default goal
make evaluate TEAM=<team>
make info
make version
make unittest                    # pytest -s -v tests
make lint                        # autoflake, black, isort
```

`make test` and `make check` do not exist. `make evaluate` on the default team exits 0 with composite 0.0, because its 191 queries have no labels ([`reports/verification.md`](reports/verification.md) section 7, item 9).

Scripts that regenerate reports (run from the repo root; each names its output in its docstring): `scripts/repro_baseline.py` (Phase 0), `scripts/eval_cv.py` (Phase 1), `scripts/error_analysis.py` (Phase 2), `scripts/cv_results.py` (Phase 3), `scripts/latency.py`, `scripts/human_kit.py`. Do not run `scripts/eval_cv.py --final`.

---

## Configuration

The served config is the two constants in [`tamu25/api/search.py`](tamu25/api/search.py): `BM25_WEIGHT = 0.10` and `MODEL_NAME = "all-MiniLM-L6-v2"`, with the model revision pinned in `MODEL_REVISION`.

[`final_config.json`](final_config.json) is **not** the served config. It still names `all-mpnet-base-v2` at 0.2/0.8, the system measured in Phase 0, and is read only by `generate_final_submission.py`. Its `training_score` (0.6638) and `improvement_over_baseline` (0.1034) are depth-50 values on all 288 training queries ([`reports/baseline_repro.json`](reports/baseline_repro.json)).

Python tooling settings (Black and isort at 120 columns, Flake8, MyPy strict) are in `pyproject.toml`. Whether the code passes strict MyPy has not been checked.

### Library API

```python
from baseline_ranker import BM25Ranker
ranker = BM25Ranker(products)                    # products: list of dicts from data/products.json
ranker.rank("organic almond milk", top_k=50)     # list of (product_id, score)

from semantic_ranker import HybridRanker
ranker = HybridRanker(products, model_name="all-MiniLM-L6-v2")
ranker.rank("organic almond milk", top_k=50, bm25_weight=0.10, semantic_weight=0.90)
```

`HybridRanker.rank` also accepts `fusion='rrf'` and `rerank=True` (the latter needs `reranker_model=`); both are off by default and not part of the final system. The scripts `baseline_ranker.py`, `semantic_ranker.py` and `generate_final_submission.py` write to team directories that do not exist, and `semantic_ranker.py` uses 0.3/0.7, not 0.10/0.90 ([`reports/adjacent_issues.md`](reports/adjacent_issues.md)).

---

## Troubleshooting

- **`ModuleNotFoundError: No module named 'tamu25'`**: run from the repo root, or `pip install -e .`.
- **`ModuleNotFoundError: google`** when running the CLI: install `google-cloud-storage`; the CLI imports it at load.
- **Model download hangs or fails**: pre-download once with `python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"`, then set `HF_HUB_OFFLINE=1`.
- **`index does not match products.json; rebuild with scripts/build_index.py`**: the API refuses to start with a stale `artifacts/index.npz`. Rebuild it.
- **Validation fails**: read the error list in `validation_report.json`. Fixture teams (`team_alpha` and others) use fixture ids and do not validate against the real catalog.

---

## Not done

- No licence file is in the repository, so no licence is granted or stated here.
- No user-history personalisation, query expansion, ANN search or fine-tuning has been built or measured.
- Cross-encoder reranking and RRF were measured and not kept (see "What was tried and not kept"). A cross-encoder tuned on grocery data was not tried.

---

## References

1. Robertson, S., & Zaragoza, H. (2009). "The Probabilistic Relevance Framework: BM25 and Beyond".
2. Reimers, N., & Gurevych, I. (2019). "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks".
3. Järvelin, K., & Kekäläinen, J. (2002). "Cumulated gain-based evaluation of IR techniques".

Libraries: [Sentence Transformers](https://www.sbert.net/), [rank-bm25](https://github.com/dorianbrown/rank_bm25), [FastAPI](https://fastapi.tiangolo.com/), [Vite](https://vite.dev/).

Repository: <https://github.com/jairajsaraf/heb-product-search>. Team VibeTribe. Thanks to the TAMU-25 H-E-B Datathon organizers and H-E-B for the dataset.
