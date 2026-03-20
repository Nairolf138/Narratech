"""Composants coeur."""

from src.core.consistency_engine import enrich
from src.core.pipeline_state import PipelineRuntimeState, PipelineStage, PipelineTransitionEvent

__all__ = ["StoryEngine", "enrich", "PipelineStage", "PipelineTransitionEvent", "PipelineRuntimeState"]


def __getattr__(name: str):
    if name == "StoryEngine":
        from src.core.story_engine import StoryEngine

        return StoryEngine
    raise AttributeError(name)
