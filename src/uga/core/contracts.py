"""Serializable data contracts. Missing observations stay unknown, never invented."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Generic, Literal, TypeVar
from uuid import uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, model_validator


def utcnow() -> datetime:
    return datetime.now(UTC)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, allow_inf_nan=False)
    schema_version: Literal["1.0"] = "1.0"


class AgentKind(StrEnum):
    PLAYER = "player"
    REVERSE = "reverse"
    BUILDER = "builder"
    WORKFLOW = "workflow"


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class TaskSpec(Contract):
    task_id: str = Field(
        default_factory=lambda: str(uuid4()), pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$"
    )
    agent: AgentKind
    operation: str = Field(min_length=1, max_length=80)
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    timeout_s: float = Field(default=120, gt=0, le=86400)
    authorized: bool = False
    created_at: AwareDatetime = Field(default_factory=utcnow)


class Point(Contract):
    x: float
    y: float


T = TypeVar("T")


class Detection(Contract, Generic[T]):
    value: T | None = None
    confidence: float = Field(ge=0, le=1)
    observed_at: AwareDatetime = Field(default_factory=utcnow)
    source: str = Field(min_length=1)

    @model_validator(mode="after")
    def unknown_has_no_confidence(self):
        if self.value is None and self.confidence != 0:
            raise ValueError("unknown values must have zero confidence")
        return self


class GameState(Contract):
    frame_id: int = Field(ge=0)
    captured_at: AwareDatetime = Field(default_factory=utcnow)
    player_position: Detection[Point] | None = None
    hp: Detection[float] | None = None
    mp: Detection[float] | None = None
    enemies: list[Detection[Point]] = Field(default_factory=list)
    items: list[Detection[Point]] = Field(default_factory=list)
    obstacles: list[tuple[int, int, int, int]] = Field(default_factory=list)
    inventory: Detection[dict[str, int]] | None = None
    map_id: Detection[str] | None = None
    ui_state: Literal["gameplay", "authentication", "disconnected", "error", "unknown"] = "unknown"
    auth_required: Detection[bool] | None = None
    goal_complete: Detection[bool] | None = None
    frame_sha256: str | None = None


class Action(StrEnum):
    WAIT = "wait"
    LEFT = "move_left"
    RIGHT = "move_right"
    UP = "move_up"
    DOWN = "move_down"
    JUMP = "jump"
    ATTACK = "attack"
    USE_ITEM = "use_item"


class ActionDecision(Contract):
    action: Action = Action.WAIT
    duration_s: float = Field(default=0.05, gt=0, le=0.25)
    confidence: float = Field(default=0, ge=0, le=1)
    reason: str
    policy: str
    based_on_frame: int = Field(ge=0)
    created_at: AwareDatetime = Field(default_factory=utcnow)


class Finding(Contract):
    subject: str
    statement: str
    source: str
    confidence: float = Field(ge=0, le=1)
    kind: Literal["fact", "hypothesis"] = "fact"


class GameSpec(Contract):
    name: str = Field(min_length=1, max_length=100)
    genre: str | None = None
    movement: dict[str, JsonValue] = Field(default_factory=dict)
    combat: dict[str, JsonValue] = Field(default_factory=dict)
    ui: list[str] = Field(default_factory=list)
    state_transitions: list[str] = Field(default_factory=list)
    systems: list[str] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)


class ArtifactReference(Contract):
    artifact_id: str = Field(default_factory=lambda: str(uuid4()))
    path: str
    media_type: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(ge=0)
    created_at: AwareDatetime = Field(default_factory=utcnow)


class AgentEvent(Contract):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    agent: AgentKind
    level: Literal["debug", "info", "warning", "error"] = "info"
    event: str
    message: str
    data: dict[str, JsonValue] = Field(default_factory=dict)
    timestamp: AwareDatetime = Field(default_factory=utcnow)


class EvaluationResult(Contract):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    benchmark: str
    seed: int
    configuration: dict[str, JsonValue] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)
    samples: int = Field(ge=1)
    passed: bool
    artifacts: list[ArtifactReference] = Field(default_factory=list)
    created_at: AwareDatetime = Field(default_factory=utcnow)


CONTRACTS = (
    TaskSpec,
    GameState,
    GameSpec,
    ActionDecision,
    AgentEvent,
    EvaluationResult,
    ArtifactReference,
)
