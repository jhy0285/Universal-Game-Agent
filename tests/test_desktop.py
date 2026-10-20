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
