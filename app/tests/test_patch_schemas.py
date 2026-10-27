from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from app.features.conditions.schemas import ConditionPatch
from app.features.presets.schemas import PresetPatch
from app.features.tasks.definitions.schemas import TaskDefinitionPatch


@pytest.mark.parametrize("model", [ConditionPatch, PresetPatch, TaskDefinitionPatch])
def test_empty_patch(model: type[BaseModel]) -> None:
    assert model.model_validate({}).model_dump(exclude_unset=True) == {}


@pytest.mark.parametrize(
    ("model", "data", "expected"),
    [
        (
            ConditionPatch,
            {"name": " Example ", "filter": " duration > 60 ", "priority": "2", "enabled": False},
            {"name": "Example", "filter": "duration > 60", "priority": 2, "enabled": False},
        ),
        (ConditionPatch, {"cli": None}, {"cli": ""}),
        (
            PresetPatch,
            {"name": " Example Preset ", "priority": "2", "cli": " --format best "},
            {"name": "example_preset", "priority": 2, "cli": "--format best"},
        ),
        (
            TaskDefinitionPatch,
            {"match_url": [" https://example.com/* "], "priority": "2"},
            {"match_url": ["https://example.com/*"], "priority": 2},
        ),
        (TaskDefinitionPatch, {"priority": None}, {"priority": 0}),
    ],
)
def test_patch_normalization(model: type[BaseModel], data: dict[str, Any], expected: dict[str, Any]) -> None:
    assert model.model_validate(data).model_dump(exclude_unset=True) == expected


@pytest.mark.parametrize(
    ("model", "data"),
    [
        (ConditionPatch, {"filter": "duration >>> 60"}),
        (ConditionPatch, {"cli": "--not-a-real-option"}),
        (ConditionPatch, {"priority": -1}),
        (ConditionPatch, {"enabled": "true"}),
        (PresetPatch, {"name": " "}),
        (PresetPatch, {"priority": -1}),
        (PresetPatch, {"cli": "--not-a-real-option"}),
        (TaskDefinitionPatch, {"priority": -1}),
        (TaskDefinitionPatch, {"match_url": ["/[/"]}),
        (TaskDefinitionPatch, {"match_url": "https://example.com/*"}),
    ],
)
def test_patch_validation(model: type[BaseModel], data: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(data)
