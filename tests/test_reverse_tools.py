import json

import pytest

from uga.agents.reverse.agent import analyze
from uga.agents.reverse.tool_analysis import analyze_with_tool
from uga.agents.reverse.toolchain import load_analysis_tools
from uga.core.contracts import TaskSpec
from uga.core.errors import AuthorizationRequired, CapabilityUnavailable
from uga.orchestrator.worker import validate_task


def test_java_declarations_handle_modifiers_without_resolving_calls(tmp_path):
    sample = tmp_path / "CombatRules.java"
    sample.write_text("""public final class CombatRules {
    public static int damage(int hp, int amount) {
        return clamp(hp - amount);
    }
    private int clamp(int hp) { return Math.max(0, hp); }
}
""")
    spec = analyze(sample, tmp_path / "analysis", authorized=True)
    assert {"damage", "clamp"} <= {finding.subject for finding in spec.findings}
    structure = json.loads((tmp_path / "analysis" / "structure.json").read_text())["sources"][0]
    assert structure["classes"][0]["name"] == "CombatRules"
    assert not structure["semantic_resolution"] and spec.genre is None


def test_tool_analysis_refuses_execution_without_complete_grant(tmp_path):
    for grants in ({}, {"approved": True}, {"approved": True, "authorized": True}):
        with pytest.raises(AuthorizationRequired):
            analyze_with_tool("ghidra", tmp_path / "sample", tmp_path / "out", **grants)
    assert not (tmp_path / "out").exists()


def test_queued_decompilation_requires_explicit_trusted_input_and_owned_tool_config(tmp_path):
    task = TaskSpec(
        agent="reverse",
        operation="decompile",
        authorized=True,
        parameters={"path": "fixture", "tool": "ghidra"},
    )
    with pytest.raises(AuthorizationRequired, match="sandbox"):
        validate_task(task)
    task.parameters["trusted_input"] = True
    validate_task(task)
    with pytest.raises(CapabilityUnavailable):
        load_analysis_tools(tmp_path)
    (tmp_path / "analysis-tools.json").write_text('{"java":"relative/path"}')
    with pytest.raises(CapabilityUnavailable, match="Invalid"):
        load_analysis_tools(tmp_path)


def test_native_normalization_keeps_provenance_and_unknown_mechanics(tmp_path, monkeypatch):
    class Analyzer:
        def __init__(self, executable):
            pass

        def analyze(self, sample, output, **grants):
            assert grants["approved"] and grants["authorized"] and grants["trusted_input"]
            return {
                "analyzed": True,
                "evidence": {
                    "functions": [
                        {"name": "take_damage", "address": "00101000", "calls": ["00101100"]},
                    ]
                },
            }

    monkeypatch.setattr("uga.agents.reverse.tool_analysis.GhidraAdapter", Analyzer)
    sample = tmp_path / "owned.bin"
    sample.write_bytes(b"unit fixture; not a real Ghidra invocation")
    spec = analyze_with_tool(
        "ghidra",
        sample,
        tmp_path / "out",
        approved=True,
        authorized=True,
        trusted_input=True,
    )
    assert spec.genre is None and not spec.movement and not spec.combat
    assert any(
        f.subject == "take_damage" and f.source.startswith("ghidra:sha256:") for f in spec.findings
    )
    raw = json.loads((tmp_path / "out" / "tool-report.json").read_text())
    assert raw["executed_target"] is False
