"""Moteur de génération narrative conforme au schéma narrative.v1."""

from __future__ import annotations

from uuid import uuid4

from src.core.io_utils import write_json_utf8


class StoryEngine:
    """Construit un payload narratif V1 à partir d'un prompt utilisateur."""

    schema_version = "narrative.v1"

    def generate(self, prompt: str) -> dict:
        """Génère une narration minimale valide et la sauvegarde sur disque."""
        if not prompt or not prompt.strip():
            raise ValueError("Le prompt doit être non vide.")

        cleaned_prompt = prompt.strip()
        scene_id = "scene_1"

        narrative = {
            "request_id": f"req_{uuid4().hex}",
            "schema_version": self.schema_version,
            "input": {
                "prompt": cleaned_prompt,
                "duration_sec": 45,
                "style": "cinematic",
                "language": "fr",
            },
            "output": {
                "synopsis": (
                    "Un protagoniste suit un indice décisif et transforme "
                    "une découverte discrète en révélation finale."
                ),
                "characters": [
                    {
                        "id": "char_1",
                        "name": "Alex",
                        "role": "protagonist",
                        "description": "Observateur persévérant qui suit chaque détail.",
                    }
                ],
                "scenes": [
                    {
                        "id": scene_id,
                        "summary": "Alex découvre un indice, l'analyse et agit.",
                        "duration_sec": 45,
                    }
                ],
                "shots": [
                    {
                        "id": "shot_001",
                        "scene_id": scene_id,
                        "description": "Plan d'ensemble: Alex arrive dans un lieu calme.",
                        "duration_sec": 12.0,
                    },
                    {
                        "id": "shot_002",
                        "scene_id": scene_id,
                        "description": "Gros plan: un indice apparaît sur la table.",
                        "duration_sec": 15.0,
                    },
                    {
                        "id": "shot_003",
                        "scene_id": scene_id,
                        "description": "Plan de conclusion: Alex prend une décision.",
                        "duration_sec": 18.0,
                    },
                ],
                "asset_refs": [
                    {
                        "id": "asset_001",
                        "type": "image",
                        "uri": "local://assets/scene/background_01.png",
                    }
                ],
                "audio_plan": {
                    "voiceover": {
                        "enabled": True,
                        "language": "fr",
                        "script": (
                            "Alex perçoit l'indice, relie les faits et agit avant qu'il ne soit trop tard."
                        ),
                    },
                    "ambience": {
                        "enabled": True,
                        "description": "Ambiance légère, tension progressive, final résolutif.",
                    },
                },
                "render_plan": {
                    "resolution": "1920x1080",
                    "fps": 24,
                    "format": "mp4",
                    "transitions": ["cut", "fade"],
                },
            },
            "provider_trace": [
                {
                    "stage": "story_generation",
                    "provider": "internal",
                    "model": "story-engine-v1",
                    "trace_id": f"trace_{uuid4().hex[:12]}",
                    "latency_ms": 42,
                }
            ],
        }

        write_json_utf8("outputs/scene.json", narrative)
        return narrative
