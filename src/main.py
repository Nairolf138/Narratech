"""Point d'entrée principal de l'application Narratech."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Callable, TypeVar
from uuid import uuid4

from src.assembly.video_assembler import assemble as assemble_video
from src.core.consistency_engine import enrich, has_blocking_violations
from src.core.input_loader import load_prompt
from src.core.io_utils import write_json_utf8
from src.core.logger import log_step, log_transition
from src.core.pipeline_state import PipelineRuntimeState, PipelineStage
from src.core.schema_validator import NarrativeValidationError, validate_narrative_document, validate_narrative_file
from src.core.story_engine import StoryEngine
from src.generation.asset_generator import generate as generate_assets
from src.generation.shot_generator import generate as generate_shots
from src.providers import (
    BaseProvider,
    MockAssetProvider,
    MockNarrativeProvider,
    MockShotProvider,
    ProviderError,
    ProviderRateLimit,
    ProviderTimeout,
)

T = TypeVar("T")


def ensure_dirs() -> None:
    """Garantit l'existence des dossiers de sortie du pipeline."""
    for path in ("outputs", "outputs/shots", "outputs/final", "assets"):
        Path(path).mkdir(parents=True, exist_ok=True)




def _assert_required_artifacts() -> None:
    """Vérifie la présence et la structure minimale des artefacts obligatoires."""
    required_paths = (
        Path("outputs/manifest.json"),
        Path("outputs/shots/shots_manifest.json"),
    )
    for required_path in required_paths:
        if not required_path.exists():
            raise RuntimeError(f"Artefact obligatoire manquant: {required_path.as_posix()}")

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


def _execute_with_retry_and_fallback(
    action: Callable[[BaseProvider], T],
    provider: BaseProvider,
    state: PipelineRuntimeState,
    stage: PipelineStage,
    fallback_provider: BaseProvider | None = None,
    retries: int = 1,
) -> T:
    """Exécute une action provider avec retry sur erreurs transitoires + fallback."""
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        try:
            return action(provider)
        except (ProviderTimeout, ProviderRateLimit) as exc:
            last_error = exc
            if attempt < retries:
                state.register_retry(stage=stage, reason=str(exc))
                time.sleep(0.01)
                continue
            break

    if fallback_provider is not None:
        return action(fallback_provider)

    if last_error is not None:
        raise last_error
    raise ProviderError("Erreur provider inconnue")


def _run_pipeline(args: list[str]) -> int:
    """Démarre le pipeline Narratech de bout en bout."""
    ensure_dirs()
    request_id = f"req_{uuid4().hex}"
    state = PipelineRuntimeState(request_id=request_id)

    def _persist_state() -> None:
        write_json_utf8("outputs/pipeline_state.json", state.to_dict())

    def _transition(to_stage: PipelineStage, reason: str) -> None:
        event = state.transition(to_stage=to_stage, reason=reason)
        log_transition(event)
        _persist_state()

    _persist_state()

    try:
        # 1) load_prompt
        log_step("chargement prompt")
        prompt = load_prompt(args)
        prompt_path = Path("outputs/prompt.txt")
        prompt_path.write_text(prompt + "\n", encoding="utf-8")
        _transition(PipelineStage.PROMPT_LOADED, "Prompt chargé avec succès")

        # Providers injectés par défaut (mock local)
        story_provider = MockNarrativeProvider()
        story_fallback_provider = MockNarrativeProvider()
        asset_provider = MockAssetProvider()
        asset_fallback_provider = MockAssetProvider()
        shot_provider = MockShotProvider()
        shot_fallback_provider = MockShotProvider()

        # 2) StoryEngine
        log_step("génération story")
        narrative = _execute_with_retry_and_fallback(
            action=lambda active_provider: StoryEngine(provider=active_provider).generate(prompt, request_id=request_id),
            provider=story_provider,
            state=state,
            stage=PipelineStage.STORY_GENERATED,
            fallback_provider=story_fallback_provider,
            retries=1,
        )
        narrative["request_id"] = request_id
        _transition(PipelineStage.STORY_GENERATED, "Narratif généré")

        # Validation schéma juste après génération
        log_step("validation schéma narratif")
        validate_narrative_document(narrative)
        _transition(PipelineStage.NARRATIVE_VALIDATED, "Schéma narratif valide")

        # 3) ConsistencyEngine
        log_step("enrichissement cohérence")
        consistency_result = enrich(narrative)
        enriched_narrative = consistency_result["enriched_doc"]
        enriched_narrative["request_id"] = request_id
        consistency_report = consistency_result["consistency_report"]
        consistency_report_path = write_json_utf8("outputs/consistency_report.json", consistency_report)
        _transition(PipelineStage.CONSISTENCY_ENRICHED, "Cohérence enrichie et rapport généré")

        if has_blocking_violations(consistency_report):
            log_step("échec cohérence bloquante")
            failure_reason = "Violations bloquantes détectées dans consistency_report"
            log_transition(state.mark_failed(stage=PipelineStage.CONSISTENCY_ENRICHED, reason=failure_reason))
            _persist_state()
            print(f"Pipeline interrompu: violations bloquantes détectées ({consistency_report_path}).")
            return 1

        # 4) AssetGenerator
        log_step("génération assets")
        asset_refs = _execute_with_retry_and_fallback(
            action=lambda active_provider: generate_assets(enriched_narrative, provider=active_provider),
            provider=asset_provider,
            state=state,
            stage=PipelineStage.ASSETS_GENERATED,
            fallback_provider=asset_fallback_provider,
            retries=1,
        )
        _transition(PipelineStage.ASSETS_GENERATED, "Assets générés")

        # 5) ShotGenerator
        log_step("génération shots")
        clips = _execute_with_retry_and_fallback(
            action=lambda active_provider: generate_shots(enriched_narrative, provider=active_provider),
            provider=shot_provider,
            state=state,
            stage=PipelineStage.SHOTS_GENERATED,
            fallback_provider=shot_fallback_provider,
            retries=1,
        )
        _transition(PipelineStage.SHOTS_GENERATED, "Shots générés")

        # 6) VideoAssembler
        log_step("assemblage final")
        final_video_path = assemble_video(clips, "outputs/final")
        _transition(PipelineStage.FINAL_ASSEMBLED, "Assemblage final terminé")

        # Passage explicite des artefacts entre modules.
        pipeline_artifacts: dict[str, dict | list | str] = {
            "request_id": request_id,
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
            "request_id": request_id,
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
        _assert_required_artifacts()

        _transition(PipelineStage.COMPLETED, "Pipeline terminé avec succès")
        log_step("fin")
        print(f"Fichier final généré: {final_video_path}")
        return 0
    except Exception as exc:
        log_transition(state.mark_failed(stage=state.current_stage, reason=str(exc)))
        _persist_state()
        raise


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
