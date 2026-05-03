"""Exécute une suite d'évaluation de prompts et produit un rapport JSON par build."""

from __future__ import annotations

import argparse
import json
import time
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.story_engine import StoryEngine


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _quality_score(narrative: dict, expected_language: str | None) -> float:
    output = narrative.get("output", {})
    scenes = output.get("scenes", [])
    shots = output.get("shots", [])
    input_payload = narrative.get("input", {})

    score = 0.0
    if isinstance(output.get("synopsis"), str) and len(output["synopsis"].strip()) >= 20:
        score += 0.4
    if isinstance(scenes, list) and len(scenes) >= 1:
        score += 0.3
    if isinstance(shots, list) and len(shots) >= 3:
        score += 0.2
    if expected_language and input_payload.get("language") == expected_language:
        score += 0.1
    return round(min(score, 1.0), 4)


def run(dataset_path: Path, output_dir: Path) -> Path:
    prompts = _load_jsonl(dataset_path)
    engine = StoryEngine()
    results: list[dict] = []

    for row in prompts:
        prompt_id = row.get("id", "unknown")
        prompt = row["prompt"]
        expected_language = row.get("expected_language")

        started = time.perf_counter()
        narrative = engine.generate(prompt=prompt, request_id=f"eval_{prompt_id}")
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)

        trace = (narrative.get("provider_trace") or [{}])[0]
        provider_latency_ms = float(trace.get("latency_ms") or 0.0)
        cost_estimate = float(trace.get("cost_estimate") or 0.0)
        quality = _quality_score(narrative, expected_language)

        results.append(
            {
                "id": prompt_id,
                "latency_ms": elapsed_ms,
                "provider_latency_ms": provider_latency_ms,
                "cost_estimate": cost_estimate,
                "quality_score": quality,
                "tags": row.get("tags", []),
            }
        )

    total = len(results) or 1
    aggregates = {
        "count": len(results),
        "avg_latency_ms": round(sum(r["latency_ms"] for r in results) / total, 3),
        "p95_latency_ms": round(sorted(r["latency_ms"] for r in results)[max(0, int(total * 0.95) - 1)], 3),
        "avg_cost_estimate": round(sum(r["cost_estimate"] for r in results) / total, 6),
        "avg_quality_score": round(sum(r["quality_score"] for r in results) / total, 4),
    }

    generated_at = datetime.now(UTC)
    report = {
        "build_date": generated_at.strftime("%Y-%m-%d"),
        "generated_at": generated_at.isoformat(),
        "dataset": dataset_path.as_posix(),
        "aggregates": aggregates,
        "results": results,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"eval_report_{generated_at.strftime('%Y%m%d')}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    latest = output_dir / "eval_report_latest.json"
    latest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="evaluation/datasets/prompts_v1.jsonl")
    parser.add_argument("--output-dir", default="outputs/evaluation")
    args = parser.parse_args()
    path = run(Path(args.dataset), Path(args.output_dir))
    print(f"Rapport d'évaluation généré: {path}")
