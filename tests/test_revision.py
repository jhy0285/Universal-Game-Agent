import hashlib
import json

import pytest

from uga.agents.builder.agent import generate, parse_requirements
from uga.agents.builder.revision import PatchPlan, TextEdit, apply_plan, revise_project
from uga.core.errors import AuthorizationRequired


def test_hash_checked_edit_keeps_original_and_preserves_other_sources(tmp_path):
    source = tmp_path / "source"
    generate(parse_requirements("2 enemies"), source)
    original = (source / "arena.json").read_bytes()
    changed = json.loads(original)
    changed["enemy_count"] = 4
    plan = PatchPlan(
        summary="Change own arena enemy count",
        edits=[
            TextEdit(
                path="arena.json",
                expected_sha256=hashlib.sha256(original).hexdigest(),
                content=json.dumps(changed),
            )
        ],
    )
    with pytest.raises(AuthorizationRequired):
        revise_project(source, tmp_path / "denied", plan)
    assert not (tmp_path / "denied").exists()
    result = revise_project(source, tmp_path / "candidate", plan, authorized=True)
    assert result["status"] == "candidate"
    assert (source / "arena.json").read_bytes() == original
    candidate = tmp_path / "candidate" / "project"
    assert json.loads((candidate / "arena.json").read_bytes())["enemy_count"] == 4
    assert (candidate / "main.gd").read_bytes() == (source / "main.gd").read_bytes()


def test_edit_rejects_changed_hash_traversal_and_partial_application(tmp_path):
    project = tmp_path / "source"
    generate(parse_requirements("arena"), project)
    path = project / "main.gd"
    before = path.read_bytes()
    good = TextEdit(
        path="main.gd", expected_sha256=hashlib.sha256(before).hexdigest(), content="modified"
    )
    bad = TextEdit(path="arena.json", expected_sha256="0" * 64, content="{}")
    with pytest.raises(ValueError, match="source hash changed"):
        apply_plan(project, PatchPlan(summary="Reject stale edits", edits=[good, bad]))
    assert path.read_bytes() == before
    for name in ("../escape.gd", "/escape.gd", "C:/escape.gd", "sub\\escape.gd", ".secret.json"):
        with pytest.raises(ValueError):
            TextEdit(path=name, expected_sha256="0" * 64, content="")
    with pytest.raises(ValueError, match="source hash changed"):
        revise_project(
            project, tmp_path / "rejected", PatchPlan(summary="stale", edits=[bad]), authorized=True
        )
    assert not (tmp_path / "rejected").exists()
