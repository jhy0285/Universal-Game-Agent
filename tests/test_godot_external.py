from pathlib import Path

import pytest

from uga.agents.builder.agent import generate, parse_requirements
from uga.agents.builder.revision import repair_project
from uga.workflows import build_play, reverse_build_play


@pytest.mark.external
def test_godot_fixture_import_and_six_engine_rules(approved_godot, tmp_path):
    project = Path(__file__).parents[1] / "test_games" / "godot"
    assert approved_godot.validate(project, approved=True)["imported"]
    result = approved_godot.smoke(project, tmp_path, approved=True)
    assert result["checks"] == 6 and result["passed"] and not result["failures"]


@pytest.mark.external
def test_generated_godot_import_rules_and_fixed_seed_play(approved_godot, tmp_path):
    project = tmp_path / "project"
    generate(parse_requirements("2D arena with 3 enemies"), project)
    approved_godot.validate(project, approved=True)
    assert approved_godot.smoke(project, tmp_path / "smoke", approved=True)["passed"]
    for seed in (7, 11, 19, 23, 31):
        result = approved_godot.play(project, tmp_path / "play", approved=True, seed=seed)
        assert result["success"] and result["truth"]["won"]
        assert result["truth"]["hp"] > 0 and not result["truth"]["enemies"]
        assert result["frames"] > 1 and result["seed_override"] == seed


@pytest.mark.external
def test_engine_build_reverse_player_and_rebuild_flow(approved_godot, tmp_path):
    result = build_play("enemies 2", tmp_path / "first", backend="godot", approved=True)
    assert result["godot_executed"] and result["engine"]["player"]["success"]
    assert result["analysis"]["combat"]["enemies"] == 2
    rebuilt = reverse_build_play(
        tmp_path / "first" / "project",
        tmp_path / "rebuilt",
        backend="godot",
        approved=True,
        authorized=True,
    )
    assert rebuilt["godot_executed"] and rebuilt["engine"]["player"]["success"]
    assert rebuilt["generated"]["spec"]["combat"]["enemies"] == 2


@pytest.mark.external
def test_builder_repairs_confirmed_engine_bug_in_a_separate_candidate(approved_godot, tmp_path):
    source = tmp_path / "broken"
    generate(parse_requirements("arena"), source)
    path = source / "main.gd"
    working = '    walls.clear()\n    if config.get("obstacles", true):\n        walls.append(Rect2(72, 28, 9, 53))'
    broken = '    walls = [Rect2(72, 28, 9, 53)] if config.get("obstacles", true) else []'
    text = path.read_text().replace(working, broken)
    path.write_text(text)
    result = repair_project(source, tmp_path / "repaired", authorized=True, approved=True)
    assert result["status"] == "verified"
    assert len(result["attempts"]) == 1 and result["attempts"][0]["patch"]["edits"]
    assert result["engine"]["smoke"]["passed"] and result["engine"]["player"]["success"]
    assert path.read_text() == text
