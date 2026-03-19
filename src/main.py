"""Point d'entrée principal de l'application Narratech."""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from typing import Callable, TypeVar
from uuid import uuid4

from src.assembly.audio_engine import build_from_audio_plan
from src.assembly.video_assembler import assemble as assemble_video
from src.core.consistency_engine import enrich, has_blocking_violations
from src.core.input_loader import load_prompt
from src.core.io_utils import write_json_utf8
from src.core.logger import log_step, log_transition
from src.core.pipeline_state import PipelineRuntimeState, PipelineStage
from src.core.schema_validator import (
    ENRICHED_SCHEMA_PATH,
    NarrativeValidationError,
    validate_narrative_document,
    validate_narrative_file,
)
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
    ProviderRequest,
    ProviderTimeout,
)

T = TypeVar("T")
DEFAULT_DEGRADED_RATIO_THRESHOLD = 0.2


def ensure_dirs() -> None:
    """Garantit l'existence des dossiers de sortie du pipeline."""
    for path in ("outputs", "outputs/shots", "outputs/audio", "outputs/final", "assets"):
        Path(path).mkdir(parents=True, exist_ok=True)


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return cleaned.strip("_") or "shot"


def _get_degraded_ratio_threshold() -> float:
    raw_value = str(Path.cwd().joinpath(".narratech_degraded_ratio_threshold").read_text(encoding="utf-8")).strip() if Path(
        ".narratech_degraded_ratio_threshold"
    ).exists() else str(DEFAULT_DEGRADED_RATIO_THRESHOLD)
    try:
        return max(0.0, float(raw_value))
    except ValueError:
        return DEFAULT_DEGRADED_RATIO_THRESHOLD


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


def _write_placeholder_clip(*, shot: dict, order: int, request_id: str, reason: str) -> dict:
    shot_id = str(shot.get("id") or f"shot_{order:03d}")
    duration = float(shot.get("duration_sec") or 0.0)
    file_path = Path("outputs/shots") / f"shot_{order:03d}_{_slugify(shot_id)[:60]}_placeholder.txt"
    file_path.write_text(
        (
            f"shot_id: {shot_id}\n"
            f"order: {order}\n"
            f"description_enriched: PLACEHOLDER ({reason})\n"
            f"duration_sec: {duration}\n"
        ),
        encoding="utf-8",
    )
    return {
        "path": file_path.as_posix(),
        "shot_id": shot_id,
        "request_id": request_id,
        "duration": duration,
        "order": order,
        "provider_trace": {"provider": "placeholder", "reason": reason},
        "latency_ms": 0,
        "cost_estimate": 0.0,
        "model_name": "placeholder",
        "quality_flag": "degraded",
    }


def _try_generate_single_shot(
    *,
    shot: dict,
    order: int,
    request_id: str,
    provider: BaseProvider,
    state: PipelineRuntimeState,
    max_retries: int,
    scope_label: str,
) -> dict:
    transient_error: Exception | None = None

    for attempt in range(1, max_retries + 2):
        try:
            shot_doc = {
                "request_id": request_id,
                "output": {
                    "shots": [shot],
                },
            }
            response = provider.generate(
                ProviderRequest(
                    request_id=request_id,
                    payload={"request_id": request_id, "output": shot_doc["output"]},
                    timeout_sec=10.0,
                )
            )
            provider_clips = response.data.get("clips") if isinstance(response.data, dict) else None
            if not isinstance(provider_clips, list) or not provider_clips:
                raise ProviderError("Le provider de shots n'a retourné aucun clip")

            payload_clip = provider_clips[0] if isinstance(provider_clips[0], dict) else {}
            shot_id = str(payload_clip.get("shot_id") or shot.get("id") or f"shot_{order:03d}")
            duration = float(payload_clip.get("duration") or shot.get("duration_sec") or 0.0)
            enriched_description = str(payload_clip.get("description_enriched") or shot.get("description") or "")
            file_path = Path("outputs/shots") / f"shot_{order:03d}_{_slugify(shot_id)[:60]}.txt"
            file_path.write_text(
                (
                    f"shot_id: {shot_id}\n"
                    f"order: {order}\n"
                    f"description_enriched: {enriched_description}\n"
                    f"duration_sec: {duration}\n"
                ),
                encoding="utf-8",
            )
            return {
                "path": file_path.as_posix(),
                "shot_id": shot_id,
                "request_id": request_id,
                "duration": duration,
                "order": order,
                "provider_trace": response.provider_trace,
                "latency_ms": response.latency_ms,
                "cost_estimate": response.cost_estimate,
                "model_name": response.model_name,
                "quality_flag": "standard",
            }
        except (ProviderTimeout, ProviderRateLimit) as exc:
            transient_error = exc
            if attempt <= max_retries:
                state.register_retry_event(
                    stage=PipelineStage.SHOTS_GENERATED,
                    reason=str(exc),
                    scope_type=scope_label,
                    scope_id=str(shot.get("id") or f"shot_{order:03d}"),
                    attempt=attempt,
                )
                time.sleep(0.01)
                continue
            break

    if transient_error is not None:
        raise transient_error
    raise ProviderError("Erreur inconnue pendant la génération du shot")


def _generate_shots_with_targeted_retries(
    *,
    scene_doc: dict,
    state: PipelineRuntimeState,
    primary_provider: BaseProvider,
    secondary_provider: BaseProvider,
    asset_provider: BaseProvider,
) -> tuple[list[dict], dict]:
    output = scene_doc.get("output")
    if not isinstance(output, dict):
        raise ValueError("scene_doc.output doit être un objet")
    shots = output.get("shots")
    if not isinstance(shots, list):
        raise ValueError("scene_doc.output.shots doit être une liste")

    Path("outputs/shots").mkdir(parents=True, exist_ok=True)
    request_id = str(scene_doc.get("request_id", "request_unknown"))
    clips: list[dict] = []
    degraded_shots = 0

    for order, shot in enumerate(shots, start=1):
        if not isinstance(shot, dict):
            continue

        generated_clip: dict | None = None

        # 1) Retry local shot sur provider primaire
        try:
            generated_clip = _try_generate_single_shot(
                shot=shot,
                order=order,
                request_id=request_id,
                provider=primary_provider,
                state=state,
                max_retries=2,
                scope_label="shot",
            )
        except (ProviderTimeout, ProviderRateLimit):
            generated_clip = None

        # 2) Fallback provider secondaire
        if generated_clip is None:
            try:
                generated_clip = _try_generate_single_shot(
                    shot=shot,
                    order=order,
                    request_id=request_id,
                    provider=secondary_provider,
                    state=state,
                    max_retries=1,
                    scope_label="shot_fallback",
                )
            except (ProviderTimeout, ProviderRateLimit):
                generated_clip = None

        # 3) Escalade asset: regénère les assets puis retente le shot
        if generated_clip is None:
            state.register_retry_event(
                stage=PipelineStage.SHOTS_GENERATED,
                reason="Escalade asset pour dépendance potentiellement invalide",
                scope_type="asset",
                scope_id=str(shot.get("id") or f"shot_{order:03d}"),
                attempt=1,
            )
            generate_assets(scene_doc, provider=asset_provider)
            try:
                generated_clip = _try_generate_single_shot(
                    shot=shot,
                    order=order,
                    request_id=request_id,
                    provider=secondary_provider,
                    state=state,
                    max_retries=0,
                    scope_label="asset_retry",
                )
            except (ProviderTimeout, ProviderRateLimit):
                generated_clip = None

        # 4) Escalade scène: tentative ciblée scène (provider primaire)
        if generated_clip is None:
            state.register_retry_event(
                stage=PipelineStage.SHOTS_GENERATED,
                reason="Escalade scène pour replanification des shots",
                scope_type="scene",
                scope_id=str(shot.get("scene_id") or "scene_unknown"),
                attempt=1,
            )
            try:
                generated_clip = _try_generate_single_shot(
                    shot=shot,
                    order=order,
                    request_id=request_id,
                    provider=primary_provider,
                    state=state,
                    max_retries=0,
                    scope_label="scene_retry",
                )
            except (ProviderTimeout, ProviderRateLimit):
                generated_clip = None

        if generated_clip is None:
            degraded_shots += 1
            generated_clip = _write_placeholder_clip(
                shot=shot,
                order=order,
                request_id=request_id,
                reason="primary+secondary indisponibles",
            )

        clips.append(generated_clip)

    shots_manifest = {
        "request_id": request_id,
        "clips": clips,
        "count": len(clips),
        "quality": {
            "degraded_shots": degraded_shots,
            "total_shots": len(clips),
            "degraded_ratio": (degraded_shots / len(clips)) if clips else 0.0,
        },
    }
    write_json_utf8("outputs/shots/shots_manifest.json", shots_manifest)
    output["clips"] = clips
    return clips, shots_manifest["quality"]


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
        validate_narrative_document(enriched_narrative, schema_path=ENRICHED_SCHEMA_PATH)
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

        # 5) ShotGenerator (retries ciblés shot > asset > scène + fallback ordonné)
        log_step("génération shots")
        clips, quality_metrics = _generate_shots_with_targeted_retries(
            scene_doc=enriched_narrative,
            state=state,
            primary_provider=shot_provider,
            secondary_provider=shot_fallback_provider,
            asset_provider=asset_provider,
        )
        state.set_degradation(
            total_shots=int(quality_metrics["total_shots"]),
            degraded_shots=int(quality_metrics["degraded_shots"]),
        )
        _transition(PipelineStage.SHOTS_GENERATED, "Shots générés")

        degraded_ratio_threshold = _get_degraded_ratio_threshold()
        if state.degraded_ratio > degraded_ratio_threshold:
            failure_reason = (
                f"Trop de shots dégradés: ratio={state.degraded_ratio:.2f} > seuil={degraded_ratio_threshold:.2f}"
            )
            log_transition(state.mark_failed(stage=PipelineStage.SHOTS_GENERATED, reason=failure_reason))
            _persist_state()
            return 1

        # 6) AudioEngine
        log_step("génération audio")
        audio_artifacts = build_from_audio_plan(enriched_narrative)

        # 7) VideoAssembler
        log_step("assemblage final")
        final_video_path = assemble_video(clips, "outputs/final", audio_artifacts=audio_artifacts)
        _transition(PipelineStage.FINAL_ASSEMBLED, "Assemblage final terminé")

        # Passage explicite des artefacts entre modules.
        pipeline_artifacts: dict[str, dict | list | str] = {
            "request_id": request_id,
            "narrative": narrative,
            "enriched_narrative": enriched_narrative,
            "asset_refs": asset_refs,
            "clips": clips,
            "audio_artifacts": audio_artifacts,
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
            "quality": {
                "degraded_shots": state.degraded_shots,
                "total_shots": state.total_shots,
                "degraded_ratio": state.degraded_ratio,
                "degraded_ratio_threshold": degraded_ratio_threshold,
            },
            "audio_dir": "outputs/audio",
            "audio_manifest_file": "outputs/audio/audio_manifest.json",
            "audio_files": [artifact.get("path") for artifact in audio_artifacts if isinstance(artifact, dict)],
            "final_dir": "outputs/final",
            "final_video_path": final_video_path,
        }
        write_json_utf8("outputs/manifest.json", manifest)
        _assert_required_artifacts()

        if state.degraded_shots > 0:
            _transition(
                PipelineStage.DONE_WITH_WARNINGS,
                f"Pipeline terminé avec dégradation ({state.degraded_shots}/{state.total_shots} shots)",
            )
        else:
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
