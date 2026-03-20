"""Point d'entrée principal de l'application Narratech."""

from __future__ import annotations

import re
import sys
import time
import os
import json
import argparse
from pathlib import Path
from contextlib import contextmanager
from collections.abc import Mapping
from typing import Callable, TypeVar
from uuid import uuid4

from src.assembly.audio_engine import build_from_audio_plan
from src.assembly.video_assembler import assemble as assemble_video
from src.core.consistency_engine import build_coherence_metrics, enrich, has_blocking_violations
from src.core.input_loader import load_prompt
from src.core.io_utils import write_json_utf8
from src.core.logger import log_step, log_transition
from src.core.pipeline_state import PipelineRuntimeState, PipelineStage
from src.core.feedback_engine import FeedbackEngine, load_feedback_input
from src.core.safety import SafetyBlockError, SafetyGuard
from src.core.recommendation_engine import RecommendationEngine
from src.core.schema_validator import (
    ENRICHED_SCHEMA_PATH,
    NarrativeValidationError,
    validate_narrative_document,
    validate_narrative_file,
)
from src.core.user_context import build_user_context
from src.config import ConfigValidationError, load_provider_bundle
from src.core.story_engine import StoryEngine
from src.generation.asset_generator import generate as generate_assets
from src.generation.shot_generator import generate as generate_shots
from src.providers import (
    BaseProvider,
    MockShotProvider,
    ProviderError,
    ProviderRateLimit,
    ProviderRequest,
    ProviderTimeout,
)
from src.providers.adapter import call_with_normalized_errors
from src.providers.contracts import AssetProviderContract, ShotProviderContract
from src.providers.trace import build_provider_trace
from src.core.provider_benchmark import aggregate_provider_benchmark, update_global_provider_benchmark

T = TypeVar("T")
DEFAULT_DEGRADED_RATIO_THRESHOLD = 0.2
EXIT_SUCCESS = 0
EXIT_USAGE_ERROR = 2
EXIT_VALIDATION_ERROR = 3
EXIT_PIPELINE_FAILURE = 10


def _build_compliance_metadata(*, session_id: str) -> dict:
    """Construit les métadonnées minimales de conformité (consentement + provenance)."""
    generated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "consent": {
            "user_consent_for_generation": True,
            "user_consent_for_export": True,
            "consent_source": "ui_session",
            "session_id": session_id,
            "captured_at": generated_at,
        },
        "provenance": {
            "input_origin": "user_prompt",
            "generation_mode": "automated_pipeline",
            "human_review_required": False,
            "generated_at": generated_at,
        },
    }


def _run_pre_publication_checks(
    *,
    enriched_narrative: dict,
    consistency_report: list[dict],
    state: PipelineRuntimeState,
    schema_narrative_valid: bool,
    schema_enriched_valid: bool,
) -> dict:
    """Exécute les checks minimaux de conformité avant export final."""
    checks = {
        "schema_narrative_valid": False,
        "schema_enriched_valid": False,
        "consent_fields_present": False,
        "consent_export_granted": False,
        "provider_trace_present": False,
        "no_blocking_consistency_violations": False,
        "degraded_ratio_within_threshold": False,
    }

    checks["schema_narrative_valid"] = schema_narrative_valid
    checks["schema_enriched_valid"] = schema_enriched_valid

    metadata = enriched_narrative.get("metadata")
    consent = metadata.get("consent") if isinstance(metadata, dict) else None
    checks["consent_fields_present"] = (
        isinstance(consent, dict)
        and isinstance(consent.get("user_consent_for_generation"), bool)
        and isinstance(consent.get("user_consent_for_export"), bool)
    )
    checks["consent_export_granted"] = bool(
        isinstance(consent, dict) and consent.get("user_consent_for_export") is True
    )

    trace = enriched_narrative.get("provider_trace")
    checks["provider_trace_present"] = isinstance(trace, list) and len(trace) > 0
    checks["no_blocking_consistency_violations"] = not has_blocking_violations(consistency_report)
    checks["degraded_ratio_within_threshold"] = state.degraded_ratio <= _get_degraded_ratio_threshold()

    failing_checks = [name for name, status in checks.items() if not status]
    status = "ok" if not failing_checks else "failed"
    result = {
        "status": status,
        "checks": checks,
        "failing_checks": failing_checks,
    }
    write_json_utf8("outputs/legal_compliance_checks.json", result)
    if failing_checks:
        raise RuntimeError(
            "Checks de conformité pré-publication en échec: " + ", ".join(failing_checks)
        )
    return result


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
        return EXIT_USAGE_ERROR

    target_file = args[0]
    try:
        validate_narrative_file(target_file)
        print(f"Document narratif valide: {target_file}")
        return EXIT_SUCCESS
    except (OSError, ValueError, NarrativeValidationError) as exc:
        print(f"Document narratif invalide: {exc}")
        return EXIT_VALIDATION_ERROR


def _build_generate_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="narratech generate", add_help=True)
    parser.add_argument("--prompt", required=True, help="Prompt principal à générer.")
    parser.add_argument(
        "--user-profile",
        required=True,
        help="Chemin vers le fichier JSON de profil utilisateur.",
    )
    parser.add_argument("--language", required=True, help="Langue cible (ex: fr, en, es).")
    parser.add_argument("--target-duration", required=True, type=int, help="Durée cible en secondes.")
    parser.add_argument("--output-dir", required=True, help="Répertoire de sortie principal.")
    return parser


def _load_user_profile_from_file(profile_path: str) -> dict:
    path = Path(profile_path)
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError("Le profil utilisateur doit être un objet JSON.")
    return payload


@contextmanager
def _working_directory(path: Path):
    current_dir = Path.cwd()
    path.mkdir(parents=True, exist_ok=True)
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(current_dir)


def _execute_with_retry_and_fallback(
    action: Callable[[BaseProvider], T],
    provider: BaseProvider,
    state: PipelineRuntimeState,
    stage: PipelineStage,
    fallback_provider: BaseProvider | None = None,
    fallback_policy: Mapping[str, object] | None = None,
    response_validator: Callable[[T], None] | None = None,
    retries: int = 1,
) -> T:
    """Exécute une action provider avec retry sur erreurs transitoires + fallback."""
    last_error: Exception | None = None
    policy = dict(fallback_policy or {})
    fallback_enabled = bool(policy.get("enabled", True))
    trigger_on_raw = policy.get("trigger_on") or ["ProviderTimeout", "ProviderRateLimit"]
    trigger_on = {
        str(item) for item in trigger_on_raw if isinstance(item, str)
    } if isinstance(trigger_on_raw, list) else {"ProviderTimeout", "ProviderRateLimit"}
    activate_after_attempt = max(1, int(policy.get("activate_after_attempt", retries + 1)))

    def _validate_response(result: T) -> T:
        if response_validator is not None:
            response_validator(result)
        return result

    def _annotate_fallback_trace(result: T, cause: Exception) -> T:
        reason = type(cause).__name__
        if hasattr(result, "provider_trace") and isinstance(getattr(result, "provider_trace"), dict):
            trace = dict(getattr(result, "provider_trace"))
            trace["fallback_mode"] = True
            trace["fallback_reason"] = reason
            setattr(result, "provider_trace", trace)
            return result
        if isinstance(result, dict):
            provider_trace = result.get("provider_trace")
            if isinstance(provider_trace, list) and provider_trace and isinstance(provider_trace[-1], dict):
                provider_trace[-1]["fallback_mode"] = True
                provider_trace[-1]["fallback_reason"] = reason
            elif isinstance(provider_trace, dict):
                provider_trace["fallback_mode"] = True
                provider_trace["fallback_reason"] = reason
        return result

    for attempt in range(retries + 1):
        try:
            return _validate_response(action(provider))
        except ProviderError as exc:
            last_error = exc
            is_transient = isinstance(exc, (ProviderTimeout, ProviderRateLimit))
            if is_transient and attempt < retries:
                state.register_retry(stage=stage, reason=str(exc))
                time.sleep(0.01)
                continue
            break

    if (
        fallback_provider is not None
        and fallback_enabled
        and last_error is not None
        and type(last_error).__name__ in trigger_on
        and (retries + 1) >= activate_after_attempt
    ):
        fallback_result = _validate_response(action(fallback_provider))
        return _annotate_fallback_trace(fallback_result, cause=last_error)

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
        "provider_trace": build_provider_trace(
            provider="placeholder",
            model="placeholder",
            latency_ms=0,
            cost_estimate=0.0,
            retries=0,
            status="degraded",
            error=reason,
            stage="shot_generation",
            reason=reason,
        ),
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
    asset_refs: list[dict],
    user_profile: dict,
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
            response = call_with_normalized_errors(
                lambda: (
                    provider.generate_shots(
                        ProviderRequest(
                            request_id=request_id,
                            payload={
                                "request_id": request_id,
                                "output": shot_doc["output"],
                                "asset_refs": asset_refs,
                                "user_profile": user_profile,
                            },
                            timeout_sec=10.0,
                        )
                    )
                    if hasattr(provider, "generate_shots")
                    else provider.generate(
                        ProviderRequest(
                            request_id=request_id,
                            payload={
                                "request_id": request_id,
                                "output": shot_doc["output"],
                                "asset_refs": asset_refs,
                                "user_profile": user_profile,
                            },
                            timeout_sec=10.0,
                        )
                    )
                )
            )
            provider_clips = response.data.get("clips") if isinstance(response.data, dict) else None
            if not isinstance(provider_clips, list) or not provider_clips:
                raise ProviderError("Le provider de shots n'a retourné aucun clip")

            payload_clip = provider_clips[0] if isinstance(provider_clips[0], dict) else {}
            shot_id = str(payload_clip.get("shot_id") or shot.get("id") or f"shot_{order:03d}")
            duration = float(payload_clip.get("duration") or shot.get("duration_sec") or 0.0)
            enriched_description = str(payload_clip.get("description_enriched") or shot.get("description") or "")
            asset_dependencies = payload_clip.get("asset_dependencies")
            if not isinstance(asset_dependencies, list):
                asset_dependencies = [
                    str(asset.get("id"))
                    for asset in asset_refs
                    if isinstance(asset, dict) and asset.get("id") is not None
                ]
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
                "asset_dependencies": asset_dependencies,
                "clip_uri": payload_clip.get("clip_uri"),
                "local_path": payload_clip.get("local_path"),
                "technical_metadata": payload_clip.get("technical_metadata", {}),
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
    primary_provider: ShotProviderContract,
    secondary_provider: ShotProviderContract,
    asset_provider: AssetProviderContract,
    asset_refs: list[dict],
    user_profile: dict,
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
    dependencies: list[dict] = []
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
                asset_refs=asset_refs,
                user_profile=user_profile,
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
                    asset_refs=asset_refs,
                    user_profile=user_profile,
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
            asset_refs = generate_assets(scene_doc, provider=asset_provider, user_profile=user_profile)
            try:
                generated_clip = _try_generate_single_shot(
                    shot=shot,
                    order=order,
                    request_id=request_id,
                    provider=secondary_provider,
                    state=state,
                    max_retries=0,
                    scope_label="asset_retry",
                    asset_refs=asset_refs,
                    user_profile=user_profile,
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
                    asset_refs=asset_refs,
                    user_profile=user_profile,
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
            generated_clip["asset_dependencies"] = [
                str(asset.get("id"))
                for asset in asset_refs
                if isinstance(asset, dict) and asset.get("id") is not None
            ]

        clips.append(generated_clip)
        dependencies.append(
            {
                "shot_id": str(generated_clip.get("shot_id") or shot.get("id") or f"shot_{order:03d}"),
                "asset_ids": list(generated_clip.get("asset_dependencies") or []),
            }
        )

    shots_manifest = {
        "request_id": request_id,
        "clips": clips,
        "count": len(clips),
        "quality": {
            "degraded_shots": degraded_shots,
            "total_shots": len(clips),
            "degraded_ratio": (degraded_shots / len(clips)) if clips else 0.0,
        },
        "asset_dependencies": dependencies,
    }
    write_json_utf8("outputs/shots/shots_manifest.json", shots_manifest)
    output["clips"] = clips
    return clips, shots_manifest["quality"]
def _run_pipeline(args: list[str], *, user_profile_payload: dict | None = None) -> int:
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

    started_at = time.perf_counter()

    try:
        # 1) load_prompt
        log_step("chargement prompt")
        prompt = load_prompt(args)
        session_id = os.getenv("NARRATECH_SESSION_ID", "session_default")
        profile_seed = dict(user_profile_payload or {})
        identity = profile_seed.get("identity") if isinstance(profile_seed.get("identity"), dict) else {}
        profile_seed["identity"] = {**identity, "session_id": session_id}
        user_profile = build_user_context(profile_seed)
        prompt_path = Path("outputs/prompt.txt")
        prompt_path.write_text(prompt + "\n", encoding="utf-8")
        _transition(PipelineStage.PROMPT_LOADED, "Prompt chargé avec succès")
        print("[1/7] Prompt et contexte utilisateur chargés")

        feedback_engine = FeedbackEngine()
        safety_guard = SafetyGuard.from_environment()
        prior_adjustments = feedback_engine.latest_adjustments_for_session(session_id=session_id)
        applied_feedback_adjustments = prior_adjustments.to_dict() if prior_adjustments is not None else None
        if prior_adjustments is not None:
            prompt = (
                f"{prompt}\n\n[AJUSTEMENTS_SESSION_PRECEDENTE]\n"
                + "\n".join(f"- {item}" for item in prior_adjustments.instructions)
            )
            log_step("ajustements de feedback appliqués depuis la session précédente")

        log_step("validation safety pre-generation")
        try:
            safety_guard.validate_prompt(prompt=prompt, request_id=request_id, session_id=session_id)
        except SafetyBlockError as exc:
            log_step("blocage safety pre-generation")
            log_transition(state.mark_failed(stage=PipelineStage.PROMPT_LOADED, reason=str(exc)))
            _persist_state()
            print(str(exc))
            print("Pipeline interrompu: blocage safety (pré-génération).")
            return 1

        # Providers injectés via configuration d'environnement (config/providers.<env>.json)
        try:
            provider_bundle = load_provider_bundle()
        except ConfigValidationError as exc:
            print(f"Configuration invalide au démarrage: {exc}")
            return EXIT_USAGE_ERROR
        story_provider = provider_bundle.story.primary
        story_fallback_provider = provider_bundle.story.fallback
        story_fallback_policy = provider_bundle.story.fallback_policy
        asset_provider = provider_bundle.asset.primary
        asset_fallback_provider = provider_bundle.asset.fallback
        asset_fallback_policy = provider_bundle.asset.fallback_policy
        shot_provider = provider_bundle.shot.primary
        shot_fallback_provider = provider_bundle.shot.fallback
        audio_provider = provider_bundle.audio.primary
        audio_timeout_sec = float(getattr(audio_provider, "_config", {}).get("timeout_sec", 10.0)) if hasattr(audio_provider, "_config") else 10.0

        # 2) StoryEngine
        log_step("génération story")
        def _generate_story(active_provider: BaseProvider) -> dict:
            engine = StoryEngine(provider=active_provider)
            try:
                return engine.generate(prompt, request_id=request_id, user_profile=user_profile)
            except TypeError:
                return engine.generate(prompt, request_id=request_id)

        narrative = _execute_with_retry_and_fallback(
            action=_generate_story,
            provider=story_provider,
            state=state,
            stage=PipelineStage.STORY_GENERATED,
            fallback_provider=story_fallback_provider,
            fallback_policy=story_fallback_policy,
            response_validator=lambda result: validate_narrative_document(result),
            retries=1,
        )
        narrative["request_id"] = request_id
        narrative["metadata"] = _build_compliance_metadata(session_id=session_id)
        _transition(PipelineStage.STORY_GENERATED, "Narratif généré")
        print("[2/7] Narratif généré")

        # Validation schéma juste après génération
        log_step("validation schéma narratif")
        validate_narrative_document(narrative)
        log_step("validation safety post-generation narrative")
        try:
            safety_guard.validate_output(payload=narrative, request_id=request_id, session_id=session_id)
        except SafetyBlockError as exc:
            log_step("blocage safety post-generation narrative")
            log_transition(state.mark_failed(stage=PipelineStage.NARRATIVE_VALIDATED, reason=str(exc)))
            _persist_state()
            print(str(exc))
            print("Pipeline interrompu: blocage safety (post-génération narrative).")
            return 1
        _transition(PipelineStage.NARRATIVE_VALIDATED, "Schéma narratif valide")

        # 3) ConsistencyEngine
        log_step("enrichissement cohérence")
        consistency_result = enrich(narrative)
        enriched_narrative = consistency_result["enriched_doc"]
        enriched_narrative["request_id"] = request_id
        enriched_narrative["metadata"] = dict(narrative.get("metadata") or {})
        validate_narrative_document(enriched_narrative, schema_path=ENRICHED_SCHEMA_PATH)
        log_step("validation safety post-generation enrichie")
        try:
            safety_guard.validate_output(payload=enriched_narrative, request_id=request_id, session_id=session_id)
        except SafetyBlockError as exc:
            log_step("blocage safety post-generation enrichie")
            log_transition(state.mark_failed(stage=PipelineStage.CONSISTENCY_ENRICHED, reason=str(exc)))
            _persist_state()
            print(str(exc))
            print("Pipeline interrompu: blocage safety (post-génération enrichie).")
            return 1
        consistency_report = consistency_result["consistency_report"]
        consistency_report_path = write_json_utf8("outputs/consistency_report.json", consistency_report)

        coherence_metrics = build_coherence_metrics(
            enriched_narrative,
            consistency_report,
            export_json=True,
        )
        recommender = RecommendationEngine()
        recommendation = recommender.recommend(
            user_id=session_id,
            generated_content=enriched_narrative,
            user_feedback={},
            coherence_metrics=coherence_metrics,
            request_id=request_id,
        )
        recommendation_payload = {
            "request_id": request_id,
            "user_id": session_id,
            "inputs": {
                "coherence_metrics": coherence_metrics,
                "feedback": {},
                "generated_content_ref": "outputs/scene_enriched.json",
                "applied_feedback_adjustments": applied_feedback_adjustments,
            },
            "outputs": recommendation.to_dict(),
            "history_preview": recommender.history_store.recent(user_id=session_id),
            "engine": "heuristic_v1",
        }
        recommendation_path = write_json_utf8("outputs/recommendation.json", recommendation_payload)

        feedback_input = load_feedback_input()
        feedback_event = feedback_engine.capture_feedback(
            request_id=request_id,
            session_id=session_id,
            feedback_payload=feedback_input,
        )
        feedback_capture_path = write_json_utf8(
            "outputs/feedback_capture.json",
            {
                "request_id": request_id,
                "session_id": session_id,
                "captured": feedback_event,
            },
        )
        feedback_audit_event = None
        if feedback_event is not None:
            next_adjustments = feedback_engine.derive_adjustments(feedback_event=feedback_event)
            feedback_audit_event = feedback_engine.audit_adjustments(
                request_id=request_id,
                session_id=session_id,
                source_request_id=request_id,
                adjustments=next_adjustments,
            )
            log_step("feedback capturé et règles d'ajustement calculées pour la session suivante")
        feedback_audit_path = write_json_utf8(
            "outputs/feedback_audit_preview.json",
            {
                "request_id": request_id,
                "session_id": session_id,
                "applied_adjustments": applied_feedback_adjustments,
                "new_audit_event": feedback_audit_event,
            },
        )

        _transition(PipelineStage.CONSISTENCY_ENRICHED, "Cohérence enrichie, rapport et recommandations générés")
        print("[3/7] Cohérence validée et enrichie")

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
            action=lambda active_provider: generate_assets(
                enriched_narrative,
                provider=active_provider,
                user_profile=user_profile,
            ),
            provider=asset_provider,
            state=state,
            stage=PipelineStage.ASSETS_GENERATED,
            fallback_provider=asset_fallback_provider,
            fallback_policy=asset_fallback_policy,
            retries=1,
        )
        _transition(PipelineStage.ASSETS_GENERATED, "Assets générés")
        print("[4/7] Assets générés")

        # 5) ShotGenerator (retries ciblés shot > asset > scène + fallback ordonné)
        log_step("génération shots")
        clips, quality_metrics = _generate_shots_with_targeted_retries(
            scene_doc=enriched_narrative,
            state=state,
            primary_provider=shot_provider,
            secondary_provider=shot_fallback_provider,
            asset_provider=asset_provider,
            asset_refs=asset_refs,
            user_profile=user_profile,
        )
        state.set_degradation(
            total_shots=int(quality_metrics["total_shots"]),
            degraded_shots=int(quality_metrics["degraded_shots"]),
        )
        _transition(PipelineStage.SHOTS_GENERATED, "Shots générés")
        print("[5/7] Shots générés")

        degraded_ratio_threshold = _get_degraded_ratio_threshold()
        if state.degraded_ratio > degraded_ratio_threshold:
            failure_reason = (
                f"Trop de shots dégradés: ratio={state.degraded_ratio:.2f} > seuil={degraded_ratio_threshold:.2f}"
            )
            log_transition(state.mark_failed(stage=PipelineStage.SHOTS_GENERATED, reason=failure_reason))
            _persist_state()
            return 1

        compliance_checks = _run_pre_publication_checks(
            enriched_narrative=enriched_narrative,
            consistency_report=consistency_report,
            state=state,
            schema_narrative_valid=True,
            schema_enriched_valid=True,
        )

        # 6) AudioEngine
        log_step("génération audio")
        audio_artifacts = build_from_audio_plan(enriched_narrative, provider=audio_provider, timeout_sec=audio_timeout_sec)
        print("[6/7] Audio généré")

        # 7) VideoAssembler
        log_step("assemblage final")
        final_video_path = assemble_video(clips, "outputs/final", audio_artifacts=audio_artifacts)
        _transition(PipelineStage.FINAL_ASSEMBLED, "Assemblage final terminé")
        print("[7/7] Assemblage final terminé")

        # Passage explicite des artefacts entre modules.
        pipeline_artifacts: dict[str, dict | list | str] = {
            "request_id": request_id,
            "narrative": narrative,
            "enriched_narrative": enriched_narrative,
            "asset_refs": asset_refs,
            "clips": clips,
            "audio_artifacts": audio_artifacts,
            "final_video_path": final_video_path,
            "assembly_manifest_file": "outputs/final/assembly_manifest.json",
            "consistency_report": consistency_report,
            "provider_bundle": provider_bundle,
        }

        scene_path = write_json_utf8("outputs/scene.json", pipeline_artifacts["narrative"])
        scene_enriched_path = write_json_utf8(
            "outputs/scene_enriched.json",
            pipeline_artifacts["enriched_narrative"],
        )

        manifest = {
            "request_id": request_id,
            "prompt_file": prompt_path.as_posix(),
            "environment": provider_bundle.environment,
            "vertical": provider_bundle.vertical,
            "scene_file": scene_path.as_posix(),
            "scene_enriched_file": scene_enriched_path.as_posix(),
            "consistency_report_file": consistency_report_path.as_posix(),
            "recommendation_file": recommendation_path.as_posix(),
            "feedback_capture_file": feedback_capture_path.as_posix(),
            "feedback_audit_file": feedback_audit_path.as_posix(),
            "safety_audit_file": "outputs/safety_audit.json",
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
            "assembly_manifest_file": "outputs/final/assembly_manifest.json",
            "success_criteria": provider_bundle.success_criteria,
            "legal_compliance_checks_file": "outputs/legal_compliance_checks.json",
            "legal_compliance_status": compliance_checks["status"],
            "total_runtime_sec": round(time.perf_counter() - started_at, 3),
        }
        provider_traces: list[dict] = []
        scene_traces = narrative.get("provider_trace")
        if isinstance(scene_traces, list):
            provider_traces.extend([trace for trace in scene_traces if isinstance(trace, dict)])
        provider_traces.extend(
            [
                asset.get("provider_trace")
                for asset in asset_refs
                if isinstance(asset, dict) and isinstance(asset.get("provider_trace"), dict)
            ]
        )
        provider_traces.extend(
            [
                clip.get("provider_trace")
                for clip in clips
                if isinstance(clip, dict) and isinstance(clip.get("provider_trace"), dict)
            ]
        )
        provider_traces.extend(
            [
                artifact.get("provider_trace")
                for artifact in audio_artifacts
                if isinstance(artifact, dict) and isinstance(artifact.get("provider_trace"), dict)
            ]
        )

        run_benchmark = aggregate_provider_benchmark(request_id=request_id, traces=provider_traces)
        write_json_utf8("outputs/benchmarks/provider_benchmark_run.json", run_benchmark)
        global_benchmark = update_global_provider_benchmark(run_benchmark=run_benchmark)
        manifest["provider_benchmark_run_file"] = "outputs/benchmarks/provider_benchmark_run.json"
        manifest["provider_benchmark_global_file"] = "outputs/benchmarks/provider_benchmark_global.json"
        manifest["provider_benchmark_totals"] = run_benchmark["totals"]
        manifest["provider_benchmark_global_totals"] = global_benchmark["totals"]

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
        print("Résumé final:")
        print(f"- final_video_path: {final_video_path}")
        print("- manifest_file: outputs/manifest.json")
        print(f"- shots_total: {state.total_shots}")
        print(f"- shots_degraded: {state.degraded_shots}")
        print(f"- runtime_sec: {manifest['total_runtime_sec']}")
        print(f"Fichier final généré: {final_video_path}")
        return EXIT_SUCCESS
    except Exception as exc:
        log_transition(state.mark_failed(stage=state.current_stage, reason=str(exc)))
        _persist_state()
        raise


def _run_generate_cli(args: list[str]) -> int:
    parser = _build_generate_parser()
    try:
        parsed = parser.parse_args(args)
    except SystemExit:
        return EXIT_USAGE_ERROR

    try:
        profile_payload = _load_user_profile_from_file(parsed.user_profile)
        profile_payload["preferences"] = (
            dict(profile_payload.get("preferences"))
            if isinstance(profile_payload.get("preferences"), dict)
            else {}
        )
        profile_payload["preferences"]["language"] = parsed.language
        profile_payload["preferences"]["duration_sec"] = parsed.target_duration
        output_dir = Path(parsed.output_dir).resolve()
        with _working_directory(output_dir):
            return _run_pipeline([parsed.prompt], user_profile_payload=profile_payload)
    except (OSError, ValueError, json.JSONDecodeError, NarrativeValidationError) as exc:
        print(f"Erreur de configuration generate: {exc}")
        return EXIT_VALIDATION_ERROR
    except Exception as exc:
        print(f"Erreur execution generate: {exc}")
        return EXIT_PIPELINE_FAILURE


def main() -> int:
    """Route vers la commande de validation ou exécute le pipeline."""
    args = sys.argv[1:]

    try:
        if args and args[0] == "validate":
            return _run_validation_cli(args[1:])
        if args and args[0] == "generate":
            return _run_generate_cli(args[1:])
        return _run_pipeline(args)

    except Exception as exc:  # gestion d'erreur globale minimale
        log_step("échec pipeline")
        print(f"Erreur pipeline: {exc}")
        return EXIT_PIPELINE_FAILURE


if __name__ == "__main__":
    sys.exit(main())
