import time
import traceback
from pathlib import Path
from typing import Literal

from pydantic import Field

from uga.core.contracts import AgentKind, Contract, GameSpec, TaskSpec
from uga.core.errors import AuthorizationRequired


class PlayerParameters(Contract):
    seed: int = 7
    max_steps: int = Field(default=600, ge=1, le=100000)
    attack_range: float = Field(default=14, ge=1, le=20)
    navigation_mode: Literal["euclidean", "geodesic"] = "euclidean"


class SoakParameters(Contract):
    seconds: float = Field(default=1800, gt=0, le=57600)


class BuilderParameters(Contract):
    requirements: str = Field(default="2D arena with 3 enemies", min_length=1, max_length=10000)
    spec: GameSpec | None = None


class BuildParameters(BuilderParameters):
    export_preset: Literal["Linux", "Windows Desktop"] | None = None


class WorkflowParameters(Contract):
    requirements: str = Field(default="2D arena with 3 enemies", min_length=1, max_length=10000)
    backend: Literal["reference", "godot"] = "reference"
    export_preset: Literal["Linux", "Windows Desktop"] | None = None


class RebuildParameters(Contract):
    path: str = Field(min_length=1, max_length=4096)
    backend: Literal["reference", "godot"] = "reference"
    export_preset: Literal["Linux", "Windows Desktop"] | None = None


class ReverseParameters(Contract):
    path: str = Field(min_length=1, max_length=4096)


def validate_task(spec: TaskSpec):
    contracts = {
        (AgentKind.PLAYER, "play"): PlayerParameters,
        (AgentKind.PLAYER, "soak"): SoakParameters,
        (AgentKind.REVERSE, "analyze"): ReverseParameters,
        (AgentKind.BUILDER, "generate"): BuilderParameters,
        (AgentKind.BUILDER, "build"): BuildParameters,
        (AgentKind.WORKFLOW, "build-play"): WorkflowParameters,
        (AgentKind.WORKFLOW, "reverse-build-play"): RebuildParameters,
    }
    model = contracts.get((spec.agent, spec.operation))
    if model is None:
        raise ValueError("unsupported agent operation")
    parameters = model.model_validate(spec.parameters)
    if (
        spec.agent == AgentKind.REVERSE
        or spec.operation in ("build", "reverse-build-play")
        or getattr(parameters, "backend", "reference") == "godot"
    ) and not spec.authorized:
        raise AuthorizationRequired(
            "Target analysis and external engine execution require explicit authorization"
        )
    if (
        spec.agent == AgentKind.WORKFLOW
        and parameters.export_preset
        and parameters.backend != "godot"
    ):
        raise ValueError("export requires the godot backend")


def execute_task(raw: dict, root: str, analysis_root: str, connection):
    """Spawn target: only registered operations, no user-supplied Python/shell code."""
    spec = TaskSpec.model_validate(raw)
    output = Path(root) / "jobs" / spec.task_id
    output.mkdir(parents=True, exist_ok=True)
    last = 0.0

    def heartbeat(tick=0):
        nonlocal last
        now = time.monotonic()
        if now - last >= 0.2:
            connection.send({"type": "heartbeat", "tick": tick})
            last = now

    def analysis_path(value):
        candidate = Path(value)
        path = (candidate if candidate.is_absolute() else Path(analysis_root) / candidate).resolve()
        if not path.is_relative_to(Path(analysis_root).resolve()):
            raise AuthorizationRequired("analysis path is outside the allowed root")
        return path

    try:
        validate_task(spec)
        heartbeat()
        if spec.agent == AgentKind.PLAYER:
            if spec.operation == "soak":
                from uga.supervisor.soak import run_soak

                result = run_soak(
                    SoakParameters.model_validate(spec.parameters).seconds,
                    output,
                    heartbeat=heartbeat,
                )
            else:
                from uga.agents.player.policies import RuleBasedPolicy
                from uga.agents.player.runner import run_episode
                from uga.test_game import ArenaConfig

                p = PlayerParameters.model_validate(spec.parameters)
                result = run_episode(
                    ArenaConfig(seed=p.seed, max_steps=p.max_steps),
                    RuleBasedPolicy(p.attack_range, p.navigation_mode),
                    output,
                    heartbeat=heartbeat,
                ).model_dump(mode="json")
        elif spec.agent == AgentKind.REVERSE:
            from uga.agents.reverse.agent import analyze

            p = ReverseParameters.model_validate(spec.parameters)
            path = analysis_path(p.path)
            result = analyze(path, output, authorized=spec.authorized).model_dump(mode="json")
        elif spec.agent == AgentKind.BUILDER:
            from uga.agents.builder.agent import generate, parse_requirements

            p = (
                BuildParameters if spec.operation == "build" else BuilderParameters
            ).model_validate(spec.parameters)
            result = generate(p.spec or parse_requirements(p.requirements), output / "project")
            if spec.operation == "build":
                from uga.agents.builder.pipeline import validate_project

                result["engine"] = validate_project(
                    output / "project",
                    output / "engine",
                    approved=spec.authorized,
                    export_preset=p.export_preset,
                    heartbeat=heartbeat,
                )
                result["built"] = "export" in result["engine"]
        else:
            from uga.workflows import build_play, reverse_build_play

            if spec.operation == "reverse-build-play":
                p = RebuildParameters.model_validate(spec.parameters)
                result = reverse_build_play(
                    analysis_path(p.path),
                    output,
                    authorized=spec.authorized,
                    heartbeat=heartbeat,
                    backend=p.backend,
                    approved=spec.authorized,
                    export_preset=p.export_preset,
                )
            else:
                p = WorkflowParameters.model_validate(spec.parameters)
                result = build_play(
                    p.requirements,
                    output,
                    heartbeat=heartbeat,
                    backend=p.backend,
                    approved=spec.authorized,
                    export_preset=p.export_preset,
                )
        connection.send({"type": "result", "result": result})
    except BaseException as exc:
        connection.send(
            {
                "type": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(limit=10),
            }
        )
    finally:
        connection.close()
