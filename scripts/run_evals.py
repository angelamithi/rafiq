"""Score Rafiq on the labelled evaluation set and write a report judges can read.

    python scripts/run_evals.py                 # offline: rules only, free, reproducible
    python scripts/run_evals.py --live          # also uses Gemini (needs GOOGLE_API_KEY); counts tokens

Writes evals/report.md and evals/report.json. Uses a throwaway database, never real users.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--price-in", type=float, default=0.30, help="USD per million input tokens (check current price)")
    ap.add_argument("--price-out", type=float, default=2.50, help="USD per million output tokens (check current price)")
    ap.add_argument("--out", default=str(ROOT / "evals"))
    args = ap.parse_args()

    from evals.cases import CASES
    from evals.harness import report, run

    results, meta = asyncio.run(run(CASES, live=args.live))
    md = report(results, meta, args.price_in, args.price_out)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(md)
    (out / "report.json").write_text(json.dumps({"meta": meta, "results": [asdict(r) for r in results]}, indent=2))
    print(md.split("\n\n")[1])
    failed = [r for r in results if not r.passed]
    for r in failed:
        print(f"FAIL {r.id}: {'; '.join(r.problems)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
