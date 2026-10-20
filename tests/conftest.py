import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--allow-godot",
        action="store_true",
        help="Explicitly approve the installed Godot binary against generated UGA fixtures",
    )


@pytest.fixture
def approved_godot(request):
    if not request.config.getoption("--allow-godot"):
        pytest.skip("Godot execution needs --allow-godot")
    from uga.agents.builder.godot import GodotAdapter

    return GodotAdapter()
