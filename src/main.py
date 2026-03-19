"""Point d'entrée principal de l'application Narratech."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src.assembly.video_assembler import assemble as assemble_video
from src.core.consistency_engine import enrich
from src.core.input_loader import load_prompt
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

        Path("outputs/scene.json").write_text(
            json.dumps(pipeline_artifacts["narrative"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        Path("outputs/scene_enriched.json").write_text(
            json.dumps(pipeline_artifacts["enriched_narrative"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        log_step("fin")
        print(f"Fichier final généré: {final_video_path}")

    except Exception as exc:  # gestion d'erreur globale minimale
        log_step("échec pipeline")
        print(f"Erreur pipeline: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
