import json

import pytest

from uga.cli import main


def test_doctor_and_schema_export(tmp_path, capsys):
    assert main(["doctor"]) == 0
    assert json.loads(capsys.readouterr().out)["version"] == "0.1.0"
    assert main(["schemas", "--output", str(tmp_path)]) == 0
    assert len(list(tmp_path.glob("*.schema.json"))) == 7


@pytest.mark.parametrize("delay", ["-1", "31", "nan", "inf"])
def test_desktop_delay_is_bounded_before_backend_initialization(delay, capsys):
    assert main(["desktop-check", "--target-pid", "42", "--start-delay", delay]) == 2
    assert "--start-delay" in capsys.readouterr().err


def test_desktop_check_waits_before_capture_and_constructs_no_input_controller(
    tmp_path, monkeypatch, capsys
):
    from uga.agents.player.perception import Frame
    from uga.core.contracts import utcnow
    from uga.test_game import ReferenceArena

    events = []

    class Backend:
        def __init__(self, pid, approved):
            assert pid == 42 and approved is True

        def client_region(self):
            assert events[0] == ("wait", 0.25)
            return {"left": 20, "top": 40, "width": 160, "height": 112}

    class Capture:
        def __init__(self, region):
            self.region = region()

        def capture(self):
            return Frame(ReferenceArena().render(), 0, utcnow())

        def close(self):
            events.append("closed")

    def forbid_controller(*args, **kwargs):
        pytest.fail("capture-only check constructed an input controller")

    monkeypatch.setattr("uga.agents.player.controller.WindowsInputBackend", Backend)
    monkeypatch.setattr(
        "uga.agents.player.controller.GuardedController.from_config", forbid_controller
    )
    monkeypatch.setattr("uga.agents.player.perception.MSSCapture", Capture)
    monkeypatch.setattr("time.sleep", lambda value: events.append(("wait", value)))
    assert (
        main(
            [
                "desktop-check",
                "--target-pid",
                "42",
                "--authorized",
                "--start-delay",
                "0.25",
                "--output",
                str(tmp_path / "probe"),
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["passed"] and output["input_sent"] is False
    assert events == [("wait", 0.25), "closed"]
