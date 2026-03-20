"""Smoke test e2e CLI du pipeline Narratech.

Prérequis d'exécution:
- Le test doit être lancé depuis le repo (ou avec `PYTHONPATH` pointant sur la racine).
- `main.py` doit être exécutable avec l'environnement provider `local` (mock-only).
- Le test force un environnement subprocess minimal pour éviter les effets de bord machine.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_json_has_keys(path: Path, required_keys: set[str]) -> dict:
    assert path.exists(), f"Artefact manquant: {path.as_posix()}"
    payload = _read_json(path)
    assert isinstance(payload, dict), f"Format inattendu pour {path.as_posix()}: dict attendu"
    missing = required_keys.difference(payload.keys())
    assert not missing, f"Clés manquantes dans {path.as_posix()}: {sorted(missing)}"
    return payload


def _assert_json_list(path: Path) -> list:
    assert path.exists(), f"Artefact manquant: {path.as_posix()}"
    payload = _read_json(path)
    assert isinstance(payload, list), f"Format inattendu pour {path.as_posix()}: liste attendue"
    return payload


def test_smoke_pipeline_cli_generates_standard_artifacts(tmp_path: Path) -> None:
    """Exécute `main.py` de bout en bout et vérifie les artefacts JSON standardisés."""

    repo_root = Path(__file__).resolve().parents[2]
    output_root = tmp_path / "run_outputs"
    output_root.mkdir(parents=True, exist_ok=True)

    fixed_prompt = "Un scientifique trouve une porte temporelle dans une cave."

    (output_root / "config").symlink_to(repo_root / "config", target_is_directory=True)

    clean_env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(repo_root),
        "NARRATECH_ENV": "local",
    }

    result = subprocess.run(
        [sys.executable, str(repo_root / "main.py"), fixed_prompt],
        cwd=output_root,
        env=clean_env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        "Le pipeline CLI a échoué de manière inattendue.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    outputs_dir = output_root / "outputs"
    shots_dir = outputs_dir / "shots"
    audio_dir = outputs_dir / "audio"

    manifest_path = outputs_dir / "manifest.json"
    scene_path = outputs_dir / "scene.json"
    enriched_scene_path = outputs_dir / "scene_enriched.json"
    consistency_report_path = outputs_dir / "consistency_report.json"
    pipeline_state_path = outputs_dir / "pipeline_state.json"
    shots_manifest_path = shots_dir / "shots_manifest.json"
    audio_manifest_path = audio_dir / "audio_manifest.json"

    manifest = _assert_json_has_keys(
        manifest_path,
        {
            "request_id",
            "environment",
            "vertical",
            "scene_file",
            "scene_enriched_file",
            "consistency_report_file",
            "shots_manifest_file",
            "audio_manifest_file",
            "final_video_path",
            "quality",
        },
    )
    request_id = str(manifest["request_id"])

    scene = _assert_json_has_keys(scene_path, {"request_id", "input", "output", "provider_trace"})
    enriched_scene = _assert_json_has_keys(enriched_scene_path, {"request_id", "input", "output", "provider_trace"})
    consistency_report = _assert_json_list(consistency_report_path)
    shots_manifest = _assert_json_has_keys(shots_manifest_path, {"request_id", "clips", "count", "asset_dependencies"})
    audio_manifest = _assert_json_has_keys(audio_manifest_path, {"request_id", "source_contract", "artifacts", "count"})
    pipeline_state = _assert_json_has_keys(
        pipeline_state_path,
        {"request_id", "current_stage", "transitions", "errors", "degraded_shots", "total_shots"},
    )

    assets_manifest_path = output_root / "assets" / request_id / "assets_manifest.json"
    _assert_json_has_keys(assets_manifest_path, {"request_id", "assets"})

    final_video_path = output_root / str(manifest["final_video_path"])
    assert final_video_path.exists(), f"Artefact final manquant: {final_video_path.as_posix()}"
    assert final_video_path.read_bytes(), "Le fichier vidéo final est vide"

    assembly_manifest_path = output_root / "outputs" / "final" / "assembly_manifest.json"
    _assert_json_has_keys(assembly_manifest_path, {"format", "video", "audio", "export"})

    assert scene["request_id"] == request_id
    assert enriched_scene["request_id"] == request_id
    assert isinstance(consistency_report, list)
    assert shots_manifest["request_id"] == request_id
    assert audio_manifest["request_id"] == request_id
    assert pipeline_state["request_id"] == request_id

    assert isinstance(shots_manifest["clips"], list) and shots_manifest["clips"], "Aucun clip généré"
    assert shots_manifest["count"] == len(shots_manifest["clips"])
    assert audio_manifest["count"] == len(audio_manifest["artifacts"])

    # Garde-fou explicite: ce smoke test doit tourner en mock-only.
    assert manifest["environment"] == "local", (
        "Ce smoke test exige l'environnement provider 'local' (mock)."
    )
    assert manifest["vertical"] == "local_mock_full", (
        "Provider mock non branché: vertical inattendue."
    )
    for index, clip in enumerate(shots_manifest["clips"]):
        trace = clip.get("provider_trace") if isinstance(clip, dict) else None
        provider_name = trace.get("provider") if isinstance(trace, dict) else None
        assert provider_name == "mock_shot_provider", (
            "Provider mock non branché correctement: "
            f"clip[{index}] utilise '{provider_name}' au lieu de 'mock_shot_provider'."
        )
