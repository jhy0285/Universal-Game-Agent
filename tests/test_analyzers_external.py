import json
import shutil
from pathlib import Path

import pytest

from uga.agents.reverse.tool_analysis import analyze_with_tool
from uga.integrations.process import run_tool


@pytest.mark.external
def test_actual_jadx_recovers_own_java_class(approved_analyzers, tmp_path):
    tools = approved_analyzers
    source = Path(__file__).parents[1] / "test_games/reverse_fixture/CombatRules.java"
    run_tool(
        [str(tools["javac"]), "--release", "11", "-d", str(tmp_path), str(source)],
        tmp_path,
        approved=True,
    )
    spec = analyze_with_tool(
        "jadx",
        tmp_path / "CombatRules.class",
        tmp_path / "analysis",
        java=tools["java"],
        installation=tools["jadx"],
        approved=True,
        authorized=True,
        trusted_input=True,
    )
    assert {"clampHp", "applyDamage", "usePotion"} <= {finding.subject for finding in spec.findings}
    assert spec.genre is None and not spec.combat


@pytest.mark.external
def test_actual_ghidra_recovers_native_functions_and_call_edges(
    approved_analyzers, tmp_path, monkeypatch
):
    tools = approved_analyzers
    compiler = shutil.which("gcc")
    assert compiler is not None, "The documented Linux fixture needs GCC"
    source = Path(__file__).parents[1] / "test_games/reverse_fixture/combat.c"
    sample = tmp_path / "combat"
    run_tool(
        [compiler, "-O0", "-g", "-fno-inline", str(source), "-o", str(sample)],
        tmp_path,
        approved=True,
    )
    monkeypatch.setenv("JAVA_HOME", str(tools["java"].parent.parent))
    output = tmp_path / ".uga" / "analysis"
    spec = analyze_with_tool(
        "ghidra",
        sample,
        output,
        executable=tools["ghidra"],
        approved=True,
        authorized=True,
        trusted_input=True,
    )
    assert {"clamp_hp", "apply_damage", "use_potion"} <= {
        finding.subject for finding in spec.findings
    }
    evidence = json.loads((output / "native/functions.json").read_text())
    functions = {item["name"]: item for item in evidence["functions"]}
    assert functions["clamp_hp"]["address"] in functions["apply_damage"]["calls"]
    assert spec.genre is None and not spec.combat
