"""Check de dérive sur latence/coût/qualité à partir du dernier rapport d'évaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

BASELINE = Path("tests/ci/eval_baseline.json")
LATEST = Path("outputs/evaluation/eval_report_latest.json")
THRESHOLDS = {
    "avg_latency_ms": 0.20,
    "avg_cost_estimate": 0.20,
    "avg_quality_score": 0.05,
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    if not LATEST.exists() or not BASELINE.exists():
        print("Baseline ou rapport courant manquant, check ignoré.")
        return 0

    baseline = _load(BASELINE)["aggregates"]
    latest = _load(LATEST)["aggregates"]

    failures: list[str] = []
    for metric, threshold in THRESHOLDS.items():
        b = float(baseline[metric])
        c = float(latest[metric])
        if metric == "avg_quality_score":
            drift = (b - c) / b if b else 0.0
            direction = "drop"
        else:
            drift = (c - b) / b if b else 0.0
            direction = "increase"
        print(f"{metric}: baseline={b:.6f}, current={c:.6f}, {direction}={drift:.2%}")
        if drift > threshold:
            failures.append(f"{metric} drift {drift:.2%} > {threshold:.2%}")

    if failures and args.strict:
        raise SystemExit("\n".join(failures))
    if failures:
        print("WARNING: dérive détectée (mode non bloquant).")
    else:
        print("Aucune dérive détectée.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
