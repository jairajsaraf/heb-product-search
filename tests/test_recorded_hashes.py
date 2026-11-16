"""The recorded sha256 values were taken on a Windows checkout with CRLF line endings.
This test recomputes them from the committed files so they can be checked on any platform."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def crlf_sha256(rel):
    b = (ROOT / rel).read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return hashlib.sha256(b).hexdigest()


def meta(name):
    return json.loads((ROOT / "reports" / name).read_text(encoding="utf-8"))["meta"]


def test_split_hash_recorded_in_reports():
    h = crlf_sha256("data/split_v1.json")
    assert meta("holdout_final.json")["split"]["sha256"] == h
    assert meta("cv_baseline.json")["split"]["sha256"] == h
    assert meta("cv_results.json")["source"]["split_sha256"] == h
    assert meta("error_analysis.json")["source"]["split_sha256"] == h


def test_cv_baseline_hash_recorded_in_reports():
    h = crlf_sha256("reports/cv_baseline.json")
    assert meta("cv_results.json")["source"]["cv_baseline_sha256"] == h
    assert meta("error_analysis.json")["source"]["cv_baseline_sha256"] == h
