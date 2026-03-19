"""Point d'entrée principal de l'application Narratech."""

from __future__ import annotations

import sys
from pathlib import Path

from src.assembly.video_assembler import assemble as assemble_video
from src.core.consistency_engine import enrich
from src.core.input_loader import load_prompt
from src.core.io_utils import write_json_utf8
from src.core.logger import log_step
from src.core.story_engine import StoryEngine
from src.generation.asset_generator import generate as generate_assets
from src.generation.shot_generator import generate as generate_shots


def ensure_dirs() -> None:
    """Garantit l'existence des dossiers de sortie du pipeline."""
    for path in ("outputs", "outputs/shots", "outputs/final", "assets"):
        Path(path).mkdir(parents=True, exist_ok=True)


def main() -> None:
    """Démarre le pipeline Narratech de bout en bout."""
    try:
        ensure_dirs()

        # 1) load_prompt
        log_step("chargement prompt")
        prompt = load_prompt(sys.argv[1:])
        prompt_path = Path("outputs/prompt.txt")
        prompt_path.write_text(prompt + "\n", encoding="utf-8")

        # 2) StoryEngine
        log_step("génération story")
        narrative = StoryEngine().generate(prompt)

        # 3) ConsistencyEngine
        log_step("enrichissement cohérence")
        enriched_narrative = enrich(narrative)

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

    except Exception as exc:  # gestion d'erreur globale minimale
        log_step("échec pipeline")
        print(f"Erreur pipeline: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
