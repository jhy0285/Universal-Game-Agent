import re
import shutil
import tempfile
from importlib.resources import files
from pathlib import Path

from uga.core.contracts import GameSpec
from uga.test_game import ArenaConfig


def parse_requirements(text: str) -> GameSpec:
    """Constrained natural-language template parser, not arbitrary game-code synthesis."""
    if not 1 <= len(text) <= 10000:
        raise ValueError("requirements must contain 1..10000 characters")
    if re.search(r"\b3D\b|\bMMORPG\b|\bUnity\b|멀티플레이어", text, re.I):
        raise ValueError("Only the original 2D top-down arena template is supported")
    match = re.search(r"(?:적|enemies)\s*(\d+)|(\d+)\s*(?:enemies|마리)", text, re.I)
    count = int(next(g for g in match.groups() if g)) if match else 3
    ArenaConfig(enemy_count=count)
    return GameSpec(
        name="UGA Test Arena",
        genre="top_down_arena",
        movement={"speed": 4, "axes": 2},
        combat={"hp": 100, "enemies": count, "attack_range": 14},
        ui=["HP", "authentication indicator", "goal status"],
        state_transitions=["playing -> won", "playing -> dead", "playing -> human_handoff"],
        systems=["movement", "collision", "combat", "healing item"],
        requirements=[text],
    )


def generate(spec: GameSpec, output: Path) -> dict:
    if spec.genre not in (None, "top_down_arena"):
        raise ValueError("Only the original top_down_arena template is implemented")
    if spec.combat.get("hp", 100) != 100 or spec.movement.get("speed", 4) != 4:
        raise ValueError("This tested template supports HP 100 and movement speed 4")
    config = ArenaConfig(
        enemy_count=spec.combat.get("enemies", 3),
        speed=spec.movement.get("speed", 4),
        attack_range=spec.combat.get("attack_range", 14),
    )
    output = output.resolve()
    if output.exists():
        raise FileExistsError("Output must be new; existing user projects are never overwritten")
    output.parent.mkdir(parents=True, exist_ok=True)
    template = Path(str(files("uga.agents.builder") / "templates" / "godot"))
    temp = Path(tempfile.mkdtemp(prefix=".uga-build-", dir=output.parent))
    try:
        shutil.copytree(template, temp, dirs_exist_ok=True)
        (temp / "game_spec.json").write_text(
            spec.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        (temp / "arena.json").write_text(config.model_dump_json(indent=2) + "\n", encoding="utf-8")
        temp.rename(output)
    finally:
        if temp.exists():
            shutil.rmtree(temp)
    return {
        "project": str(output),
        "engine": "godot4",
        "generated": True,
        "built": False,
        "spec": spec.model_dump(mode="json"),
        "template": "original-arena-v1",
        "limitations": [
            "template generation; arbitrary game synthesis and repair are not implemented"
        ],
    }
