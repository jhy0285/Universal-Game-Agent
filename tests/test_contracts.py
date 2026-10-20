import pytest
from pydantic import ValidationError

from uga.core.contracts import (
    CONTRACTS,
    ActionDecision,
    AgentKind,
    Detection,
    GameSpec,
    GameState,
    TaskSpec,
)


def test_contract_round_trip_and_unknown_state():
    task = TaskSpec(agent=AgentKind.PLAYER, operation="play", parameters={"seed": 7})
    assert TaskSpec.model_validate_json(task.model_dump_json()) == task
    state = GameState(frame_id=0)
    assert state.hp is None and state.auth_required is None
    assert GameSpec(name="unknown").genre is None
    for model in CONTRACTS:
        assert model.model_json_schema()["properties"]["schema_version"]["const"] == "1.0"


@pytest.mark.parametrize(
    "values",
    [
        {"duration_s": 30},
        {"confidence": 1.1},
        {"action": "modify_memory"},
        {"unexpected": 1},
        {"created_at": "2026-10-20T00:00:00"},
    ],
)
def test_action_contract_rejects_unsafe_or_invalid_data(values):
    with pytest.raises(ValidationError):
        ActionDecision(reason="test", policy="test", based_on_frame=0, **values)


def test_detection_does_not_fabricate_confidence():
    with pytest.raises(ValidationError):
        Detection[float](value=None, confidence=0.9, source="test")
    assert Detection[float](value=None, confidence=0, source="test").value is None


def test_timeout_and_nonfinite_values_rejected():
    with pytest.raises(ValidationError):
        TaskSpec(agent="player", operation="play", timeout_s=0)
    with pytest.raises(ValidationError):
        ActionDecision(reason="test", policy="test", based_on_frame=0, confidence=float("nan"))
