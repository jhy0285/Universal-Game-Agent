from uga.agents.player.desktop import run_desktop
from uga.agents.player.perception import Frame, PixelPerception
from uga.agents.player.policies import RuleBasedPolicy
from uga.core.contracts import utcnow
from uga.test_game import ReferenceArena


class Capture:
    def __init__(self, game):
        self.game, self.closed = game, False

    def capture(self):
        return Frame(self.game.render(), self.game.tick, utcnow())

    def close(self):
        self.closed = True


class Controller:
    def __init__(self, game):
        self.game, self.stopped, self.actions = game, False, 0

    def perform(self, action, state):
        self.actions += 1
        self.game.step(action.action)

    def emergency_stop(self):
        self.stopped = True


def test_desktop_loop_hands_off_authentication_before_any_input(tmp_path):
    game = ReferenceArena()
    game.auth_required = True
    capture, controller = Capture(game), Controller(game)
    result = run_desktop(
        capture, PixelPerception(), RuleBasedPolicy(), controller, tmp_path, max_seconds=1
    )
    assert result["stop_reason"] == "human_handoff" and controller.actions == 0
    assert controller.stopped and capture.closed and (tmp_path / "human-handoff.json").is_file()


def test_scaled_known_fixture_keeps_observations():
    from PIL import Image

    image = ReferenceArena().render().resize((640, 448), Image.Resampling.NEAREST)
    state = PixelPerception().analyze(Frame(image, 0, utcnow()))
    assert state.player_position.value.x == 20 and state.hp.value == 100


def test_capture_only_preflight_records_preview_and_never_needs_a_controller(tmp_path):
    from uga.agents.player.desktop import check_desktop

    for name, game, expected in [
        ("ready", ReferenceArena(), True),
        ("auth", ReferenceArena(), False),
        ("won", ReferenceArena(), False),
    ]:
        game.auth_required = name == "auth"
        if name == "won":
            game.enemies.clear()
        capture = Capture(game)
        result = check_desktop(capture, PixelPerception(), tmp_path / name)
        assert result["passed"] is expected and result["input_sent"] is False
        assert capture.closed and (tmp_path / name / "preview.png").is_file()
        assert (tmp_path / name / "state.json").is_file()


def test_preflight_rejects_unknown_pixels_and_closes_on_existing_output(tmp_path):
    import pytest
    from PIL import Image

    from uga.agents.player.desktop import check_desktop

    class Unknown(Capture):
        def capture(self):
            return Frame(Image.new("RGB", (160, 112)), 0, utcnow())

    capture = Unknown(None)
    result = check_desktop(capture, PixelPerception(), tmp_path / "unknown")
    assert not result["ready_for_input"] and result["reason"] == "unsupported_or_unready_frame"
    assert capture.closed
    capture = Capture(ReferenceArena())
    with pytest.raises(FileExistsError):
        check_desktop(capture, PixelPerception(), tmp_path / "unknown")
    assert capture.closed


def test_desktop_region_defaults_to_client_and_rejects_outside_roi():
    import pytest

    from uga.agents.player.desktop import desktop_region
    from uga.core.errors import SafetyStop

    class Window:
        def client_region(self):
            return {"left": -640, "top": 20, "width": 640, "height": 448}

    window = Window()
    assert desktop_region(window) == window.client_region()
    assert desktop_region(window, window.client_region()) == window.client_region()
    for changes in ({"left": -641}, {"width": 641}, {"height": 0}, {"top": 19}):
        with pytest.raises(SafetyStop, match="inside"):
            desktop_region(window, {**window.client_region(), **changes})


def test_mss_resolves_window_after_initialization_and_refreshes_before_each_frame(monkeypatch):
    import sys
    from types import SimpleNamespace

    from uga.agents.player.perception import MSSCapture

    calls, grabbed = [], []

    class MSS:
        def __init__(self):
            calls.append("mss")

        def grab(self, region):
            grabbed.append(region)
            image = ReferenceArena().render()
            return SimpleNamespace(size=image.size, rgb=image.tobytes())

        def close(self):
            calls.append("closed")

    def region():
        assert calls[0] == "mss"
        calls.append("region")
        return {"left": len(calls), "top": 0, "width": 160, "height": 112}

    monkeypatch.setitem(sys.modules, "mss", SimpleNamespace(mss=MSS))
    capture = MSSCapture(region)
    try:
        first, second = capture.capture(), capture.capture()
        assert first.frame_id == 0 and second.frame_id == 1
        assert grabbed[0]["left"] != grabbed[1]["left"]
    finally:
        capture.close()
    assert calls[-1] == "closed"


def test_mss_closes_when_region_resolution_fails(monkeypatch):
    import sys
    from types import SimpleNamespace

    import pytest

    from uga.agents.player.perception import MSSCapture

    closed = []
    monkeypatch.setitem(
        sys.modules,
        "mss",
        SimpleNamespace(mss=lambda: SimpleNamespace(close=lambda: closed.append(True))),
    )
    with pytest.raises(ValueError, match="positive"):
        MSSCapture({"left": 0, "top": 0, "width": 0, "height": 112})
    assert closed == [True]


def test_windows_key_events_carry_scan_codes_for_physical_key_games():
    import json
    from pathlib import Path

    import pytest

    from uga.agents.player.controller import WINDOWS_KEYS, keyboard_fields
    from uga.core.errors import SafetyStop

    assert keyboard_fields("LEFT", False) == (0x25, 0x4B, 0x0001)
    assert keyboard_fields("LEFT", True) == (0x25, 0x4B, 0x0003)
    assert keyboard_fields("Z", False) == (0x5A, 0x2C, 0)
    assert keyboard_fields("SPACE", True) == (0x20, 0x39, 0x0002)
    with pytest.raises(SafetyStop):
        keyboard_fields("F4", False)
    actions = json.loads((Path(__file__).parents[1] / "configs/actions.json").read_text())
    assert set(actions["actions"].values()) <= set(WINDOWS_KEYS)
