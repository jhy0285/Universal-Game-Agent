import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--allow-godot",
        action="store_true",
        help="Explicitly approve the installed Godot binary against generated UGA fixtures",
    )
    parser.addoption(
        "--allow-analyzers",
        action="store_true",
        help="Approve the documented JADX/Ghidra/JDK toolchain on original UGA fixtures",
    )


@pytest.fixture
def approved_analyzers(request):
    if not request.config.getoption("--allow-analyzers"):
        pytest.skip("External analysis needs --allow-analyzers")
    from pathlib import Path

    root = Path(__file__).parents[1]
    paths = {
        "java": root / ".uga/tools/jdk/jdk-21.0.12.1+1/bin/java",
        "javac": root / ".uga/tools/jdk/jdk-21.0.12.1+1/bin/javac",
        "jadx": root / ".uga/tools/jadx/1.5.6",
        "ghidra": root / ".uga/tools/ghidra/ghidra_12.1.4_PUBLIC/support/analyzeHeadless",
    }
    assert all(path.exists() for path in paths.values()), "Configure the documented toolchain first"
    return paths


@pytest.fixture
def approved_godot(request):
    if not request.config.getoption("--allow-godot"):
        pytest.skip("Godot execution needs --allow-godot")
    from uga.agents.builder.godot import GodotAdapter

    return GodotAdapter()
