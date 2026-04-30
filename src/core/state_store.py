"""Persistance JSON de l'état runtime du pipeline."""

from __future__ import annotations

from pathlib import Path

from src.core.io_utils import write_json_utf8
from src.core.pipeline_state import PipelineRuntimeState


class PipelineStateStore:
    """Stockage JSON du `PipelineRuntimeState`."""

    def __init__(self, path: str | Path = "outputs/pipeline_state.json") -> None:
        self.path = Path(path)

    def save(self, state: PipelineRuntimeState) -> Path:
        """Sauvegarde l'état courant."""
        return write_json_utf8(self.path, state.to_dict())

    def load(self) -> PipelineRuntimeState:
        """Recharge l'état depuis le disque."""
        payload = PipelineRuntimeState.read_json_file(self.path)
        if not isinstance(payload, dict):
            raise ValueError("Le fichier d'état pipeline doit contenir un objet JSON.")
        return PipelineRuntimeState.from_dict(payload)
