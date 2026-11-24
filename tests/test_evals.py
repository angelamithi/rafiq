"""The labelled evaluation set must stay at 100% (run in its own process: it uses its own settings and database)."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_eval_set_passes(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_evals.py"), "--out", str(tmp_path)],
                       capture_output=True, text=True, timeout=600, cwd=ROOT)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    report = (tmp_path / "report.md").read_text()
    assert "cases passed (100%)" in report and "| complete |" in report and "| out of context |" in report
