import re


def test_makefile_data_paths_exist(repo_root):
    text = (repo_root / "Makefile").read_text()
    paths = re.findall(r"^\w+\s*\??=\s*(data/\S+)", text, re.M)
    assert len(paths) >= 3, paths
    missing = [p for p in paths if not (repo_root / p).exists()]
    assert not missing, missing
    team = re.search(r"^TEAM\s*\?=\s*(\S+)", text, re.M).group(1)
    assert (repo_root / "teams" / team / "submission.json").exists()
