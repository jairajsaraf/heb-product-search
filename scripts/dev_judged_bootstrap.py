"""Paired bootstrap of the tuned hybrid (out of fold) against BM25 on the 230 dev queries, judged-only and composite.

  python scripts/dev_judged_bootstrap.py   # writes reports/dev_judged_bootstrap.json

The dev judged-only difference was never bootstrapped in the committed reports; this reports it next to the
locked one. The composite is a cross-check: it must equal the bootstrap in reports/cv_baseline.json.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]

import eval_cv as E  # noqa: E402

SRC = ROOT / "reports/cv_baseline.json"
OUT = ROOT / "reports/dev_judged_bootstrap.json"
METRICS = ("judged_only", "composite")


def compute():
    raw = SRC.read_bytes().replace(b"\r\n", b"\n")
    oof = json.loads(raw)["per_query_oof"]
    out = {"source": SRC.name, "source_sha256": hashlib.sha256(raw).hexdigest(), "n_queries": len(oof)}
    for m in METRICS:
        b = E.paired_bootstrap([q["tuned_hybrid_oof"][m] for q in oof.values()], [q["bm25"][m] for q in oof.values()])
        out.update(resamples=b["resamples"], seed=b["seed"])
        out[m] = {k: b[k] for k in ("mean_diff", "ci95", "frac_resamples_gt0")}
    return out


if __name__ == "__main__":
    OUT.write_text(json.dumps(compute(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
