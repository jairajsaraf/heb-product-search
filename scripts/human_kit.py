"""Phase 6b (spec M12): blind human comparison kit on 10 seeded test queries.

  .venv/Scripts/python scripts/build_index.py   # once: artifacts/index.npz
  .venv/Scripts/python scripts/human_kit.py     # writes reports/human_kit.md and reports/human_kit_key.json

Sides: BM25 (BM25Ranker.rank) vs the final system (Searcher.search, the API path), top 10 each. The spec's sides
(tuned baseline vs final) are the same system, see reports/holdout_prereg.md. Each system is side A for half the
queries, in a seeded shuffled order; the key goes to a separate file. Uses test queries only (no labels exist).
"""
import html
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from baseline_ranker import BM25Ranker, load_json  # noqa: E402
from tamu25.api.app import build_searcher  # noqa: E402
from tamu25.api.search import BM25_WEIGHT, MODEL_NAME, MODEL_REVISION  # noqa: E402

SEED, N_QUERIES, K = 20261113, 10, 10
KIT, KEY = ROOT / "reports/human_kit.md", ROOT / "reports/human_kit_key.json"


def main():
    final = build_searcher(ROOT / "data", ROOT / "artifacts/index.npz")
    bm25 = BM25Ranker(final.products)
    by_id = {p["product_id"]: p for p in final.products}
    rng = random.Random(SEED)
    queries = rng.sample(sorted(load_json(ROOT / "data/queries_synth_test.json"), key=lambda q: q["query_id"]),
                         N_QUERIES)
    side_a = ["bm25", "final"] * (N_QUERIES // 2)  # balanced: each system is side A for half the queries
    random.Random(SEED + 1).shuffle(side_a)

    def cell(pid):
        p = by_id[pid]
        return html.unescape(f"{p['title']} · {p.get('brand') or 'no brand'}").replace("\xa0", " ").replace("|", "/")

    lines = [
        "# Blind comparison kit",
        "",
        f"{N_QUERIES} search queries, two result lists each (top {K}). One list comes from each of two ranking "
        "systems; which system is A and which is B changes from query to query. Do not open "
        "`human_kit_key.json` until you have answered every query.",
        "",
        "**Rubric:** for each query, *which list would you buy from?* Answer `A`, `B` or `same`. Judge the list as a "
        "shopper would: are the products what you asked for, and are the best ones near the top?",
        "",
    ]
    key = []
    for n, q in enumerate(queries, 1):
        sides = {"bm25": [p for p, _ in bm25.rank(q["query"], top_k=K)],
                 "final": [r["product_id"] for r in final.search(q["query"], K)["results"]]}
        a = side_a[n - 1]
        b = "final" if a == "bm25" else "bm25"
        key.append({"n": n, "query_id": q["query_id"], "query": q["query"], "A": a, "B": b,
                    "identical_lists": sides["bm25"] == sides["final"]})
        lines += [f"## {n}. {q['query']}", "", "| # | List A | List B |", "|---|---|---|"]
        lines += [f"| {i} | {cell(x)} | {cell(y)} |" for i, (x, y) in enumerate(zip(sides[a], sides[b]), 1)]
        lines += ["", "Which list would you buy from? `A` / `B` / `same`: ____", ""]

    KIT.write_text("\n".join(lines), encoding="utf-8")
    KEY.write_text(json.dumps({
        "seed": SEED,
        "method": f"random.Random({SEED}): sample {N_QUERIES} of the test queries sorted by query_id; side A is a "
                  f"balanced list (each system {N_QUERIES // 2} times) shuffled with random.Random({SEED + 1})",
        "systems": {"bm25": "BM25Ranker.rank (baseline_ranker.py)",
                    "final": f"Searcher.search: linear BM25 + {MODEL_NAME} at {MODEL_REVISION}, BM25 weight "
                             f"{BM25_WEIGHT}"},
        "queries": key}, indent=2), encoding="utf-8")
    print(f"wrote {KIT.name} and {KEY.name}: {N_QUERIES} queries, "
          f"{sum(k['identical_lists'] for k in key)} with identical lists")


if __name__ == "__main__":
    main()
