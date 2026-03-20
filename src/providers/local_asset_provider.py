"""Provider asset concret avec rendu local déterministe ou mode API simulé."""

from __future__ import annotations

import html
import json
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from uuid import uuid4

from src.providers.adapter import call_with_normalized_errors
from src.providers.base import BaseProvider, ProviderHealth, ProviderInvalidResponse, ProviderRequest, ProviderResponse
from src.providers.contracts import AssetProviderContract


class LocalAssetProvider(BaseProvider, AssetProviderContract):
    """Génère des assets image persistants avec prompts cohérents et reproductibles."""

    def __init__(self, transport: Callable[..., Mapping[str, object]] | None = None) -> None:
        self._transport = transport
        self._config: dict[str, object] = {
            "mode": "local",
            "asset_root": "assets",
            "api_base_url": "https://asset-provider.local",
            "default_seed": 1337,
            "deterministic_params": {
                "width": 1024,
                "height": 1024,
                "steps": 30,
                "cfg_scale": 7.5,
                "sampler": "ddim",
            },
        }

    def configure(self, config: Mapping[str, object]) -> None:
        merged = dict(self._config)
        merged.update(dict(config))
        params = merged.get("deterministic_params")
        if not isinstance(params, dict):
            params = dict(self._config["deterministic_params"])
        merged["deterministic_params"] = dict(params)
        self._config = merged

    def generate_assets(self, request: ProviderRequest) -> ProviderResponse:
        return call_with_normalized_errors(lambda: self._generate_assets_impl(request))

    def _generate_assets_impl(self, request: ProviderRequest) -> ProviderResponse:
        output = request.payload.get("output")
        if not isinstance(output, dict):
            raise ProviderInvalidResponse("payload.output doit être un objet")

        request_id = str(request.payload.get("request_id") or request.request_id)
        base_seed = int(request.payload.get("seed") or self._config.get("default_seed") or 0)
        generation_params = self._resolve_generation_params(request.payload)
        mode = str(self._config.get("mode") or "local")

        start = time.perf_counter()
        assets: list[dict] = []

        characters = output.get("characters") if isinstance(output.get("characters"), list) else []
        for index, character in enumerate(characters, start=1):
            if not isinstance(character, dict):
                continue
            seed = base_seed + index
            asset_id = f"asset_character_{index:03d}"
            prompt = self._build_character_prompt(output=output, character=character)
            self._validate_prompt(prompt=prompt, character=character)
            assets.append(
                self._materialize_asset(
                    request_id=request_id,
                    asset_id=asset_id,
                    asset_type="character",
                    prompt=prompt,
                    seed=seed,
                    generation_params=generation_params,
                    mode=mode,
                )
            )

        scene_seed = base_seed + len(assets) + 1
        env_prompt = self._build_environment_prompt(output=output)
        assets.append(
            self._materialize_asset(
                request_id=request_id,
                asset_id="asset_environment_001",
                asset_type="environment",
                prompt=env_prompt,
                seed=scene_seed,
                generation_params=generation_params,
                mode=mode,
            )
        )

        latency_ms = int((time.perf_counter() - start) * 1000)
        model_name = "local-asset-v2"
        return ProviderResponse(
            data={"request_id": request_id, "assets": assets},
            provider_trace={
                "stage": "asset_generation",
                "provider": "local_asset_provider",
                "model": model_name,
                "trace_id": f"trace_{uuid4().hex[:12]}",
                "mode": mode,
                "deterministic": True,
            },
            latency_ms=latency_ms,
            cost_estimate=0.0,
            model_name=model_name,
        )

    def _resolve_generation_params(self, payload: Mapping[str, object]) -> dict[str, object]:
        config_params = self._config.get("deterministic_params")
        params = dict(config_params) if isinstance(config_params, dict) else {}
        payload_params = payload.get("generation_params")
        if isinstance(payload_params, dict):
            params.update(payload_params)
        return params

    def _extract_primary_packet(self, output: Mapping[str, object]) -> dict[str, object]:
        shots = output.get("shots") if isinstance(output.get("shots"), list) else []
        for shot in shots:
            if isinstance(shot, dict) and isinstance(shot.get("consistency_packet"), dict):
                return dict(shot["consistency_packet"])
        return {}

    def _build_character_prompt(self, *, output: Mapping[str, object], character: Mapping[str, object]) -> str:
        packet = self._extract_primary_packet(output)
        character_id = str(character.get("id") or "unknown_character")
        character_name = str(character.get("name") or character_id)

        packet_chars = packet.get("characters") if isinstance(packet.get("characters"), list) else []
        packet_character = next(
            (
                item
                for item in packet_chars
                if isinstance(item, dict)
                and (item.get("character_id") == character_id or item.get("display_name") == character_name)
            ),
            {},
        )

        traits = packet_character.get("core_traits") if isinstance(packet_character.get("core_traits"), list) else []
        if not traits:
            role = character.get("role")
            traits = [str(role)] if isinstance(role, str) and role.strip() else []

        clothing = (
            packet_character.get("signature_clothing")
            if isinstance(packet_character.get("signature_clothing"), list)
            else []
        )
        palette = packet_character.get("color_palette") if isinstance(packet_character.get("color_palette"), list) else []

        visual = packet.get("visual_continuity") if isinstance(packet.get("visual_continuity"), dict) else {}
        mood = str(visual.get("mood_tone") or "mood neutre")
        lighting = str(visual.get("lighting_profile") or "cinematic soft key light")

        scenes = output.get("scenes") if isinstance(output.get("scenes"), list) else []
        environment = ""
        if scenes and isinstance(scenes[0], dict):
            environment = str(scenes[0].get("summary") or "")

        return (
            f"Character concept art for {character_name} ({character_id}).\n"
            f"Scene context: {environment}.\n"
            f"Mood: {mood}. Lighting: {lighting}.\n"
            f"Palette: {', '.join(str(item) for item in palette) or 'N/A'}.\n"
            f"Signature clothing: {', '.join(str(item) for item in clothing) or 'N/A'}.\n"
            f"Expected core traits: {', '.join(str(item) for item in traits) or 'N/A'}.\n"
            "Respect strict de la continuité inter-scènes."
        )

    def _build_environment_prompt(self, *, output: Mapping[str, object]) -> str:
        packet = self._extract_primary_packet(output)
        visual = packet.get("visual_continuity") if isinstance(packet.get("visual_continuity"), dict) else {}

        scenes = output.get("scenes") if isinstance(output.get("scenes"), list) else []
        synopsis = str(output.get("synopsis") or "")
        scene_summary = ""
        if scenes and isinstance(scenes[0], dict):
            scene_summary = str(scenes[0].get("summary") or "")

        return (
            "Environment matte painting.\n"
            f"Narrative synopsis: {synopsis}.\n"
            f"Scene environment: {scene_summary}.\n"
            f"Mood: {str(visual.get('mood_tone') or 'tension contenue')}.\n"
            f"Lighting profile: {str(visual.get('lighting_profile') or 'cinematic soft key light')}.\n"
            f"Camera style: {str(visual.get('camera_style') or 'cinematic dolly')}.\n"
            "Respect strict de la continuité inter-scènes."
        )

    def _validate_prompt(self, *, prompt: str, character: Mapping[str, object]) -> None:
        expected_name = str(character.get("name") or character.get("id") or "").strip()
        if expected_name and expected_name.lower() not in prompt.lower():
            raise ProviderInvalidResponse(
                f"Prompt de personnage invalide: nom attendu absent ({expected_name})."
            )

        role = character.get("role")
        if isinstance(role, str) and role.strip() and role.lower() not in prompt.lower():
            raise ProviderInvalidResponse(
                f"Prompt de personnage invalide: trait attendu absent ({role})."
            )

    def _materialize_asset(
        self,
        *,
        request_id: str,
        asset_id: str,
        asset_type: str,
        prompt: str,
        seed: int,
        generation_params: Mapping[str, object],
        mode: str,
    ) -> dict:
        target_dir = Path(str(self._config.get("asset_root") or "assets")) / request_id
        target_dir.mkdir(parents=True, exist_ok=True)

        image_path = target_dir / f"{asset_id}.svg"
        metadata_path = target_dir / f"{asset_id}.metadata.json"

        api_image_uri = ""
        if mode == "api":
            api_image_uri = self._api_generate_asset(
                request_id=request_id,
                asset_id=asset_id,
                prompt=prompt,
                seed=seed,
                generation_params=generation_params,
            )

        image_path.write_text(self._build_svg(prompt=prompt, seed=seed), encoding="utf-8")
        metadata = {
            "asset_id": asset_id,
            "type": asset_type,
            "request_id": request_id,
            "mode": mode,
            "prompt": prompt,
            "seed": seed,
            "generation_params": dict(generation_params),
            "api_image_uri": api_image_uri,
            "image_uri": f"local://{image_path.as_posix()}",
        }
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "id": asset_id,
            "type": asset_type,
            "file_name": image_path.name,
            "uri": f"local://{image_path.as_posix()}",
            "metadata_uri": f"local://{metadata_path.as_posix()}",
            "seed": seed,
            "generation_params": dict(generation_params),
            "payload": metadata,
        }

    def _api_generate_asset(
        self,
        *,
        request_id: str,
        asset_id: str,
        prompt: str,
        seed: int,
        generation_params: Mapping[str, object],
    ) -> str:
        if self._transport is not None:
            result = self._transport(
                request_id=request_id,
                asset_id=asset_id,
                prompt=prompt,
                seed=seed,
                generation_params=dict(generation_params),
            )
            image_uri = result.get("image_uri") if isinstance(result, Mapping) else None
            if isinstance(image_uri, str) and image_uri:
                return image_uri

        api_base_url = str(self._config.get("api_base_url") or "https://asset-provider.local").rstrip("/")
        return f"{api_base_url}/v1/assets/{request_id}/{asset_id}?seed={seed}"

    def _build_svg(self, *, prompt: str, seed: int) -> str:
        escaped = html.escape(prompt[:600])
        return (
            "<svg xmlns='http://www.w3.org/2000/svg' width='1024' height='1024'>"
            "<rect width='100%' height='100%' fill='#141414'/>"
            f"<text x='40' y='80' fill='#ffffff' font-size='28'>Narratech Asset</text>"
            f"<text x='40' y='130' fill='#9ED2C6' font-size='20'>seed={seed}</text>"
            f"<foreignObject x='40' y='180' width='944' height='780'><div xmlns='http://www.w3.org/1999/xhtml' "
            "style='color:#eeeeee;font-family:monospace;font-size:16px;white-space:pre-wrap'>"
            f"{escaped}</div></foreignObject></svg>"
        )

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        return self.generate_assets(request)

    def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(ok=True, details={"provider": "local_asset_provider", "mode": self._config.get("mode")})
