"""The harness's pinned embedding revisions match the snapshots recorded in the reports and the API pin."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import semantic_ranker  # noqa: E402
from tamu25.api import search  # noqa: E402


def test_pins_match_report_meta():
    for name in ("cv_baseline", "cv_results", "holdout_final"):
        meta = json.loads((ROOT / "reports" / f"{name}.json").read_text(encoding="utf-8"))["meta"]
        assert semantic_ranker.MODEL_REVISIONS == {m["name"]: m["revision"] for m in meta["models"].values()}, name


def test_minilm_pin_matches_api():
    assert semantic_ranker.MODEL_REVISIONS["all-MiniLM-L6-v2"] == search.MODEL_REVISION
