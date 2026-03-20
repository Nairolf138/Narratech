"""Script de démonstration unique (happy path) pour Narratech."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_PROMPT = (
    "Un détective découvre un indice visuel, relie les événements et conclut par une révélation claire."
)


def _coherence_score(report: object) -> float:
    violations = report if isinstance(report, list) else []
    blocking = sum(1 for item in violations if isinstance(item, dict) and item.get("severity") == "blocking")
    major = sum(1 for item in violations if isinstance(item, dict) and item.get("severity") == "major")
    score = 1.0 - (blocking * 0.4 + major * 0.2)
    return max(0.0, round(score, 3))


def main() -> int:
    prompt = " ".join(sys.argv[1:]).strip() or DEFAULT_PROMPT
    env = dict(os.environ)
    env["NARRATECH_ENV"] = "demo"

    started = time.perf_counter()
    result = subprocess.run([sys.executable, "-m", "src.main", prompt], text=True, capture_output=True, env=env, check=False)
    runtime = time.perf_counter() - started

    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        print("❌ Démo échouée: le pipeline a retourné un code non nul.")
        return result.returncode

    manifest = json.loads(Path("outputs/manifest.json").read_text(encoding="utf-8"))
    shots_manifest = json.loads(Path("outputs/shots/shots_manifest.json").read_text(encoding="utf-8"))
    consistency_report = json.loads(Path("outputs/consistency_report.json").read_text(encoding="utf-8"))

    criteria = manifest.get("success_criteria", {})
    total_shots = int(shots_manifest.get("count") or 0)
    degraded_ratio = float((shots_manifest.get("quality") or {}).get("degraded_ratio") or 0.0)
    coherence = _coherence_score(consistency_report)

    checks = {
        "temps_total": runtime <= float(criteria.get("max_total_runtime_sec", 30)),
        "nombre_de_shots": total_shots == int(criteria.get("expected_shot_count", 3)),
        "placeholders": degraded_ratio <= float(criteria.get("max_placeholder_ratio", 0.2)),
        "coherence": coherence >= float(criteria.get("min_coherence_score", 0.8)),
    }

    print("=== Demo happy path ===")
    print(f"Prompt: {prompt}")
    print(f"Verticale: {manifest.get('vertical')} (env={manifest.get('environment')})")
    print(f"Temps total: {runtime:.2f}s")
    print(f"Shots: {total_shots}")
    print(f"Ratio placeholders: {degraded_ratio:.2%}")
    print(f"Score cohérence: {coherence:.3f}")
    for key, ok in checks.items():
        print(f" - {key}: {'OK' if ok else 'KO'}")

    if all(checks.values()):
        print("✅ Démo réussie.")
        return 0

    print("❌ Démo incomplète: au moins un critère est KO.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
