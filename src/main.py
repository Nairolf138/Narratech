"""Point d'entrée principal de l'application Narratech."""

from __future__ import annotations

import sys
from pathlib import Path

from src.assembly.video_assembler import assemble as assemble_video
from src.core.consistency_engine import enrich, has_blocking_violations
from src.core.input_loader import load_prompt
from src.core.io_utils import write_json_utf8
from src.core.logger import log_step
from src.core.schema_validator import NarrativeValidationError, validate_narrative_file
from src.core.schema_validator import validate_narrative_document
from src.core.story_engine import StoryEngine
from src.generation.asset_generator import generate as generate_assets
from src.generation.shot_generator import generate as generate_shots


def ensure_dirs() -> None:
    """Garantit l'existence des dossiers de sortie du pipeline."""
    for path in ("outputs", "outputs/shots", "outputs/final", "assets"):
        Path(path).mkdir(parents=True, exist_ok=True)


def _run_validation_cli(args: list[str]) -> int:
    """Valide un fichier narratif depuis la ligne de commande."""
    if len(args) != 1:
        print("Usage: narratech validate <file>")
        return 1

    target_file = args[0]
    try:
        validate_narrative_file(target_file)
        print(f"Document narratif valide: {target_file}")
        return 0
    except (OSError, ValueError, NarrativeValidationError) as exc:
        print(f"Document narratif invalide: {exc}")
        return 1


def _run_pipeline(args: list[str]) -> int:
    """Démarre le pipeline Narratech de bout en bout."""
    ensure_dirs()

    # 1) load_prompt
    log_step("chargement prompt")
    prompt = load_prompt(args)
    prompt_path = Path("outputs/prompt.txt")
    prompt_path.write_text(prompt + "\n", encoding="utf-8")

    # 2) StoryEngine
    log_step("génération story")
    narrative = StoryEngine().generate(prompt)

    # Validation schéma juste après génération
    log_step("validation schéma narratif")
    validate_narrative_document(narrative)

    # 3) ConsistencyEngine
    log_step("enrichissement cohérence")
    consistency_result = enrich(narrative)
    enriched_narrative = consistency_result["enriched_doc"]
    consistency_report = consistency_result["consistency_report"]
    consistency_report_path = write_json_utf8("outputs/consistency_report.json", consistency_report)

    if has_blocking_violations(consistency_report):
        log_step("échec cohérence bloquante")
        print(f"Pipeline interrompu: violations bloquantes détectées ({consistency_report_path}).")
        return 1

    # 4) AssetGenerator
    log_step("génération assets")
    asset_refs = generate_assets(enriched_narrative)

    # 5) ShotGenerator
    log_step("génération shots")
    clips = generate_shots(enriched_narrative)

    # 6) VideoAssembler
    log_step("assemblage final")
    final_video_path = assemble_video(clips, "outputs/final")

    # Passage explicite des artefacts entre modules.
    pipeline_artifacts: dict[str, dict | list | str] = {
        "narrative": narrative,
        "enriched_narrative": enriched_narrative,
        "asset_refs": asset_refs,
        "clips": clips,
        "final_video_path": final_video_path,
        "consistency_report": consistency_report,
    }

    scene_path = write_json_utf8("outputs/scene.json", pipeline_artifacts["narrative"])
    scene_enriched_path = write_json_utf8(
        "outputs/scene_enriched.json",
        pipeline_artifacts["enriched_narrative"],
    )

    manifest = {
        "prompt_file": prompt_path.as_posix(),
        "scene_file": scene_path.as_posix(),
        "scene_enriched_file": scene_enriched_path.as_posix(),
        "consistency_report_file": consistency_report_path.as_posix(),
        "assets_dir": "assets",
        "asset_refs": [asset.get("uri") for asset in asset_refs if isinstance(asset, dict)],
        "shots_dir": "outputs/shots",
        "shot_files": [clip.get("path") for clip in clips if isinstance(clip, dict)],
        "shots_manifest_file": "outputs/shots/shots_manifest.json",
        "final_dir": "outputs/final",
        "final_video_path": final_video_path,
    }
    write_json_utf8("outputs/manifest.json", manifest)

    log_step("fin")
    print(f"Fichier final généré: {final_video_path}")
    return 0


def main() -> int:
    """Route vers la commande de validation ou exécute le pipeline."""
    args = sys.argv[1:]

    try:
        if args and args[0] == "validate":
            return _run_validation_cli(args[1:])
        return _run_pipeline(args)

    except Exception as exc:  # gestion d'erreur globale minimale
        log_step("échec pipeline")
        print(f"Erreur pipeline: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
