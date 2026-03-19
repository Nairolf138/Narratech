"""Vérifie les seuils de couverture par sous-module critique."""

from __future__ import annotations

import json
from pathlib import Path

COVERAGE_PATH = Path("coverage.json")
THRESHOLDS = {
    "src/core": 85.0,
    "src/generation": 80.0,
}


def main() -> int:
    if not COVERAGE_PATH.exists():
        raise SystemExit("coverage.json introuvable. Exécuter pytest avec --cov-report=json:coverage.json.")

    report = json.loads(COVERAGE_PATH.read_text(encoding="utf-8"))
    files = report.get("files", {})

    failures: list[str] = []
    for module_prefix, minimum in THRESHOLDS.items():
        relevant = [stats["summary"] for file_name, stats in files.items() if file_name.startswith(module_prefix)]

        if not relevant:
            failures.append(f"Aucun fichier couvert pour le module {module_prefix}.")
            continue

        covered = sum(item.get("covered_lines", 0) for item in relevant)
        total = sum(item.get("num_statements", 0) for item in relevant)
        pct = (covered / total * 100.0) if total else 0.0

        print(f"{module_prefix}: {pct:.2f}% (seuil {minimum:.2f}%)")
        if pct < minimum:
            failures.append(
                f"Couverture insuffisante pour {module_prefix}: {pct:.2f}% < {minimum:.2f}%"
            )

    if failures:
        raise SystemExit("\n".join(failures))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
