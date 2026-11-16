import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import dev_judged_bootstrap  # noqa: E402


@pytest.fixture(scope="module")
def got():
    return dev_judged_bootstrap.compute()


def test_matches_committed_json(got):
    want = json.loads((ROOT / "reports/dev_judged_bootstrap.json").read_text(encoding="utf-8"))
    assert got["source_sha256"] == want["source_sha256"]
    assert (got["n_queries"], got["resamples"], got["seed"]) == (want["n_queries"], want["resamples"], want["seed"])
    for m in dev_judged_bootstrap.METRICS:
        assert got[m]["mean_diff"] == pytest.approx(want[m]["mean_diff"], abs=5e-5)
        assert got[m]["ci95"] == pytest.approx(want[m]["ci95"], abs=5e-5)
        assert got[m]["frac_resamples_gt0"] == pytest.approx(want[m]["frac_resamples_gt0"], abs=5e-5)


def test_composite_reproduces_harness(got):
    c = got["composite"]
    assert round(c["mean_diff"], 4) == 0.0717
    assert [round(x, 4) for x in c["ci95"]] == [0.0552, 0.0886]
