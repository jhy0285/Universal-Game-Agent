import json
import zipfile

import pytest

from uga.agents.builder.agent import generate, parse_requirements
from uga.agents.builder.godot import GodotAdapter
from uga.agents.reverse.agent import analyze
from uga.core.contracts import TaskSpec
from uga.core.errors import AuthorizationRequired
from uga.integrations.process import run_tool
from uga.orchestrator.worker import validate_task
from uga.workflows import build_play, reverse_build_play


def test_builder_generates_playable_sources_without_overwriting(tmp_path):
    spec = parse_requirements("적 4마리가 있는 2D 게임")
    project = tmp_path / "game"
    result = generate(spec, project)
    assert result["generated"] and not result["built"]
    assert json.loads((project / "arena.json").read_text())["enemy_count"] == 4
    assert (project / "main.gd").is_file() and (project / "smoke_test.gd").is_file()
    with pytest.raises(FileExistsError):
        generate(spec, project)
    with pytest.raises(ValueError):
        parse_requirements("enemies 9999")


def test_authorized_source_and_apk_analysis(tmp_path):
    project = tmp_path / "game"
    generate(parse_requirements("arena"), project)
    with pytest.raises(AuthorizationRequired):
        analyze(project, tmp_path / "denied")
    report = analyze(project, tmp_path / "analysis", authorized=True)
    assert any(f.subject == "step" for f in report.findings)
    assert report.genre == "top_down_arena"
    assert any("runtime behavior not verified" in f.statement for f in report.findings)
    apk = tmp_path / "sample.apk"
    with zipfile.ZipFile(apk, "w") as archive:
        archive.writestr("classes.dex", b"dex\n035\0fixture")
        archive.writestr("assets/own.txt", "original fixture")
    analyze(apk, tmp_path / "apk", authorized=True)
    structure = json.loads((tmp_path / "apk" / "structure.json").read_text())
    assert structure["sources"][0]["dex_files"] == ["classes.dex"]
    assert structure["sources"][0]["decompiled"] is False
    assert structure["executed_samples"] is False


def test_archive_traversal_and_expansion_rejected(tmp_path):
    bad = tmp_path / "bad.apk"
    with zipfile.ZipFile(bad, "w") as archive:
        archive.writestr("../escape", "x")
    with pytest.raises(ValueError, match="unsafe"):
        analyze(bad, tmp_path / "out", authorized=True)
    with zipfile.ZipFile(bad, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("a", b"0" * 100000)
    with pytest.raises(ValueError, match="expansion"):
        analyze(bad, tmp_path / "out", authorized=True)


def test_external_execution_requires_approval_before_any_process(tmp_path):
    with pytest.raises(AuthorizationRequired):
        run_tool(["/nonexistent/godot"], tmp_path)
    adapter = GodotAdapter(tmp_path / "nonexistent")
    with pytest.raises(AuthorizationRequired):
        adapter.smoke(tmp_path, tmp_path / "report")


@pytest.mark.integration
def test_build_reverse_player_artifact_flow(tmp_path):
    result = build_play("2 enemies", tmp_path)
    assert result["reference_player"]["success"]
    assert result["analysis"]["findings"]
    assert result["godot_executed"] is False


def test_reverse_builder_player_preserves_source_configuration(tmp_path):
    generate(parse_requirements("enemies 2"), tmp_path / "source")
    result = reverse_build_play(tmp_path / "source", tmp_path / "rebuild", authorized=True)
    assert result["generated"]["spec"]["combat"]["enemies"] == 2
    assert result["reference_player"]["success"] and not result["godot_executed"]


def test_engine_workflow_requires_approval_before_generation(tmp_path):
    with pytest.raises(AuthorizationRequired):
        build_play("2 enemies", tmp_path / "denied", backend="godot")
    assert not (tmp_path / "denied").exists()
    with pytest.raises(ValueError, match="export requires"):
        build_play("arena", tmp_path / "denied", export_preset="Linux")
    for agent, operation, parameters in (
        ("builder", "build", {}),
        ("workflow", "build-play", {"backend": "godot"}),
        ("workflow", "reverse-build-play", {"path": "test_games/godot"}),
    ):
        task = TaskSpec(agent=agent, operation=operation, parameters=parameters)
        with pytest.raises(AuthorizationRequired):
            validate_task(task)
        task.authorized = True
        validate_task(task)
