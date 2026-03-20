"""Provider narratif OpenAI conforme au contrat `generate_narrative`."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Mapping
from typing import Any
from urllib import error, request
from uuid import uuid4

from src.core.schema_validator import NarrativeValidationError, validate_narrative_document
from src.providers.adapter import call_with_normalized_errors
from src.providers.base import (
    BaseProvider,
    ProviderAuthError,
    ProviderHealth,
    ProviderInvalidResponse,
    ProviderRateLimit,
    ProviderRequest,
    ProviderResponse,
    ProviderTimeout,
)
from src.providers.contracts import NarrativeProviderContract

TransportFn = Callable[[dict[str, Any], float, str, str], dict[str, Any]]


class OpenAINarrativeProvider(BaseProvider, NarrativeProviderContract):
    """Provider de narration basé sur l'API Responses d'OpenAI."""

    def __init__(self, transport: TransportFn | None = None) -> None:
        self._transport = transport or self._default_transport
        self._config: dict[str, Any] = {
            "model": "gpt-4.1-mini",
            "endpoint": "https://api.openai.com/v1/responses",
            "temperature": 0.2,
            "max_remediation_attempts": 1,
            "include_prompt_in_trace": True,
        }

    def configure(self, config: Mapping[str, Any]) -> None:
        self._config.update(dict(config))
        api_key = str(self._config.get("api_key") or os.getenv("OPENAI_API_KEY") or "").strip()
        if not api_key:
            raise ProviderAuthError("Configuration invalide: clé API OpenAI manquante.")
        self._config["api_key"] = api_key

    def generate_narrative(self, request_obj: ProviderRequest) -> ProviderResponse:
        return call_with_normalized_errors(lambda: self._generate_narrative_impl(request_obj))

    def _generate_narrative_impl(self, request_obj: ProviderRequest) -> ProviderResponse:
        prompt = request_obj.payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ProviderInvalidResponse("payload.prompt doit être une chaîne non vide")

        duration_sec = int(request_obj.payload.get("duration_sec", 45))
        style = str(request_obj.payload.get("style") or "cinematic")
        language = str(request_obj.payload.get("language") or "fr")

        timeout_sec = float(request_obj.timeout_sec or 20.0)
        model_name = str(self._config.get("model") or "gpt-4.1-mini")
        endpoint = str(self._config.get("endpoint") or "https://api.openai.com/v1/responses")
        api_key = str(self._config.get("api_key") or "")
        temperature = float(self._config.get("temperature", 0.2))
        max_remediation_attempts = int(self._config.get("max_remediation_attempts", 1))

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            request_id=request_obj.request_id,
            prompt=prompt.strip(),
            duration_sec=duration_sec,
            style=style,
            language=language,
        )

        start = time.perf_counter()
        usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        last_error = ""
        raw_text = ""

        for attempt in range(max_remediation_attempts + 1):
            payload = self._build_api_payload(
                model=model_name,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
            )
            api_response = self._transport(payload, timeout_sec, api_key, endpoint)
            usage = self._extract_usage(api_response, existing_usage=usage)
            raw_text = self._extract_text(api_response)

            try:
                document = self._parse_and_validate_document(raw_text)
                latency_ms = int((time.perf_counter() - start) * 1000)
                trace_entry = {
                    "stage": "story_generation",
                    "provider": "openai_narrative_provider",
                    "model": model_name,
                    "trace_id": f"trace_{uuid4().hex[:12]}",
                    "latency_ms": latency_ms,
                }
                document["provider_trace"] = [trace_entry]

                provider_trace = {
                    "stage": "story_generation",
                    "provider": "openai_narrative_provider",
                    "model": model_name,
                    "trace_id": trace_entry["trace_id"],
                    "latency_ms": latency_ms,
                    "usage": usage,
                    "attempts": attempt + 1,
                }
                if bool(self._config.get("include_prompt_in_trace", True)):
                    provider_trace["prompt"] = {
                        "system": system_prompt,
                        "user": user_prompt,
                    }

                return ProviderResponse(
                    data=document,
                    provider_trace=provider_trace,
                    latency_ms=latency_ms,
                    cost_estimate=0.0,
                    model_name=model_name,
                )
            except (json.JSONDecodeError, NarrativeValidationError, ProviderInvalidResponse) as exc:
                last_error = str(exc)
                if attempt >= max_remediation_attempts:
                    break
                user_prompt = self._build_remediation_prompt(
                    base_user_prompt=user_prompt,
                    invalid_json=raw_text,
                    validation_error=last_error,
                )

        raise ProviderInvalidResponse(
            f"Impossible d'obtenir un JSON narratif valide après remédiation: {last_error}"
        )

    def generate(self, request_obj: ProviderRequest) -> ProviderResponse:
        return self.generate_narrative(request_obj)

    def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(
            ok=bool(self._config.get("api_key")),
            details={
                "provider": "openai_narrative_provider",
                "model": self._config.get("model", "gpt-4.1-mini"),
                "endpoint": self._config.get("endpoint", "https://api.openai.com/v1/responses"),
            },
        )

    def _build_system_prompt(self) -> str:
        return (
            "Tu es un moteur de génération narrative strict. "
            "Tu DOIS répondre avec un JSON brut valide (aucun markdown, aucun texte hors JSON) "
            "conforme au schéma narrative.v1: racine avec request_id, schema_version='narrative.v1', "
            "input, output, provider_trace. Respecte les contraintes: 1 scene, 1-2 characters, "
            "duration scene 30-60 sec, shots avec duration_sec > 0, audio_plan et render_plan complets. "
            "N'ajoute aucune propriété hors schéma."
        )

    def _build_user_prompt(
        self,
        *,
        request_id: str,
        prompt: str,
        duration_sec: int,
        style: str,
        language: str,
    ) -> str:
        return (
            "Génère un document narratif JSON conforme.\n"
            f"request_id={request_id}\n"
            f"prompt={prompt}\n"
            f"duration_sec={duration_sec}\n"
            f"style={style}\n"
            f"language={language}\n"
            "Assure-toi que provider_trace existe et contient au moins un événement."
        )

    def _build_remediation_prompt(self, *, base_user_prompt: str, invalid_json: str, validation_error: str) -> str:
        return (
            f"{base_user_prompt}\n\n"
            "Le JSON précédent est invalide. Corrige-le et réponds UNIQUEMENT avec un JSON valide.\n"
            f"Erreur de validation: {validation_error}\n"
            f"JSON invalide: {invalid_json}"
        )

    def _build_api_payload(self, *, model: str, system_prompt: str, user_prompt: str, temperature: float) -> dict[str, Any]:
        return {
            "model": model,
            "temperature": temperature,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                },
            ],
            "text": {"format": {"type": "json_object"}},
        }

    def _parse_and_validate_document(self, raw_text: str) -> dict[str, Any]:
        normalized = raw_text.strip()
        if normalized.startswith("```"):
            normalized = normalized.strip("`")
            normalized = normalized.replace("json\n", "", 1).strip()

        document = json.loads(normalized)
        if not isinstance(document, dict):
            raise ProviderInvalidResponse("Le provider doit renvoyer un objet JSON racine.")

        validate_narrative_document(document)
        return document

    def _extract_text(self, api_response: dict[str, Any]) -> str:
        if isinstance(api_response.get("output_text"), str):
            return str(api_response["output_text"])

        output = api_response.get("output")
        if isinstance(output, list):
            collected: list[str] = []
            for item in output:
                if not isinstance(item, dict):
                    continue
                content = item.get("content")
                if not isinstance(content, list):
                    continue
                for block in content:
                    if isinstance(block, dict) and isinstance(block.get("text"), str):
                        collected.append(block["text"])
            if collected:
                return "\n".join(collected)

        raise ProviderInvalidResponse("Réponse OpenAI sans contenu textuel exploitable.")

    def _extract_usage(self, api_response: dict[str, Any], *, existing_usage: dict[str, int]) -> dict[str, int]:
        usage = api_response.get("usage")
        if not isinstance(usage, dict):
            return existing_usage

        updated = dict(existing_usage)
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            value = usage.get(key)
            if isinstance(value, int):
                updated[key] = updated.get(key, 0) + value
        return updated

    def _default_transport(
        self,
        payload: dict[str, Any],
        timeout_sec: float,
        api_key: str,
        endpoint: str,
    ) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            endpoint,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=timeout_sec) as response:  # noqa: S310
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as http_exc:
            status = getattr(http_exc, "code", None)
            if status in {401, 403}:
                raise ProviderAuthError("Authentification OpenAI invalide.") from http_exc
            if status == 429:
                raise ProviderRateLimit("Quota OpenAI dépassé.") from http_exc
            if status in {408, 504}:
                raise ProviderTimeout("Timeout OpenAI.") from http_exc
            raise ProviderInvalidResponse(f"Erreur HTTP OpenAI inattendue ({status}).") from http_exc
        except TimeoutError as timeout_exc:
            raise ProviderTimeout("Timeout OpenAI.") from timeout_exc

