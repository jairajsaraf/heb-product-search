# Adjacent issues (listed, not fixed)

Phase 4 scope is the Makefile, README and `final_config.json` only. Everything here is left as found. "Confirmed" means read or measured in the file or report named; "inferred" means reasoned, not run.

## From the spec's seed list (confirmed by reading the file named)

- `baseline_ranker.py:165`, `semantic_ranker.py:158`: write to `teams/team-gsr/`, which does not exist.
- `generate_final_submission.py:67`: writes to `teams/VibeTribe/`, which does not exist.
- `generate_final_submission.py:76-80`: calls `py` (Windows only) and omits the `--products` and `--queries_synth` arguments the CLI requires.
- `generate_final_submission.py:23`: prints a fraction with a percent sign.
- `tamu25/cli/main.py:10`: imports `google.cloud.storage` at module load, so `validate` and `evaluate` need that package.
- `tamu25/cli/main.py:136-204`: `download_gcs_file` ignores `credentials_path` and swallows its own exceptions.
- `tamu25/evaluate.py:52`: queries missing from a submission are silently not scored.
- `tamu25/metrics.py:19`: nDCG ideal built from the submitted list.
- `poetry.lock` is tracked although `.gitignore` lists it; it cannot be regenerated here (no `poetry`), so it is stale.
- `.claude/settings.local.json` is tracked.
- README: `make test` and `make check` do not exist; CLI examples do not match the real flags; "8 teams" (6 directories); "90%+ coverage" and the runtime table are unsourced; `BM25Ranker` and `HybridRanker` signatures are wrong; GitLab links while `origin` is GitHub; licence and author placeholders.

Fixed in Phase 4 and so removed from the list: `.PHONY` omitting `lint` and `unittest`; the unused `QREAL` and `LREAL`.

## Found while doing Phase 4

- `generate_final_submission.py:14-24` reads `final_config.json` and formats `training_score` with `.4f` and `improvement_over_baseline` with `:+.2f`. Both keys therefore had to stay. `improvement_over_baseline` is a fraction (0.1034), so the script prints "+0.10". Confirmed by reading the script.
- The same script ranks with `final_config.json`'s `model` (mpnet), which is not the Phase 3 final system (tuned MiniLM). Confirmed from `reports/cv_results.md`.
- The old default `TEAM=team_alpha` failed validation on the real data (fixture ids such as `Q001`/`0001`, 4 queries). Confirmed by running `tamu25 validate`. Only `team-git-em` validates against the real catalog, and it covers the 191 test queries, so `make evaluate` (train labels) cannot score it. `team_bravo`, `team_charlie`, `team_delta` and `team_echo` were not checked.
- README "Optimization Process" (12 configurations) and the Benchmarks table are unsourced. Not checked against `reports/`.

## Found in Phases 1-3 (confirmed by those sessions)

1. `create_product_text` (`baseline_ranker.py`) drops the `safety_warning` field (allergen "Contains:" lists).
2. `preprocess_text` keeps hyphenated words as single tokens: `gluten-free` appears in 100 products, `gluten` in 321.
3. The catalog `brand` field holds 23 descriptor values such as "Fresh", "Natural", "Wild", "Frozen" and "USDA" (`reports/error_analysis.json`, `meta.rules.not_brands`).
4. Product titles contain HTML entities (`&ndash;`, `&nbsp;`, `&eacute;`) that become tokens.
5. sentence-transformers makes Hugging Face Hub metadata requests even for cached models unless `HF_HUB_OFFLINE=1` is set.
6. `scripts/eval_cv.py --final` has never been run or tested (meant for Phase 6).
7. `scripts/eval_cv.py` imports the private `_build_label_lookup` from `tamu25/evaluate.py`.
8. `semantic_ranker.py` now imports `CrossEncoder` at module load.
9. Label holes: about 7 of the 230 dev queries have a top 10 that is mostly unjudged (`reports/error_analysis.md`).
