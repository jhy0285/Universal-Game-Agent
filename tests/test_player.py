import threading
import time
from datetime import timedelta

import pytest
from PIL import Image

from uga.agents.player.controller import GuardedController
from uga.agents.player.perception import Frame, PixelPerception
from uga.agents.player.policies import LayaPolicy, RuleBasedPolicy, SafeFallbackPolicy
from uga.agents.player.runner import run_episode
from uga.core.contracts import Action, ActionDecision, utcnow
from uga.core.errors import AuthorizationRequired, CapabilityUnavailable, SafetyStop
from uga.test_game import ArenaConfig, ReferenceArena


def observed(game=None):
    game = game or ReferenceArena()
    return PixelPerception().analyze(Frame(game.render(), game.tick, utcnow()))


@pytest.mark.parametrize("seed", [7, 11, 19, 23, 31])
def test_pixel_player_wins_with_ground_truth(seed):
    result = run_episode(ArenaConfig(seed=seed))
    assert result.success, result.model_dump()
    assert result.perception_accuracy == 1
    assert result.verified_effects > 3
    assert result.metrics["end_to_end_p99_ms"] > 0


def test_unknown_pixels_and_authentication_fail_closed():
    engine = PixelPerception()
    state = engine.analyze(Frame(Image.new("RGB", (160, 112)), 0, utcnow()))
    assert state.hp is None
    assert RuleBasedPolicy().decide(state).action == Action.WAIT
    game = ReferenceArena()
    game.auth_required = True
    state = observed(game)
    assert state.auth_required.value is True
    assert RuleBasedPolicy().decide(state).action == Action.WAIT


def test_roi_cache_does_not_reuse_hud_and_items_work():
    game = ReferenceArena()
    engine = PixelPerception()
    engine.analyze(Frame(game.render(), 0, utcnow()))
    game.hp = 32
    state = engine.analyze(Frame(game.render(), 1, utcnow()))
    assert engine.cache_hits == 1 and state.hp.value == 32
    game.player = list(game.items[0])
    assert game.step(Action.USE_ITEM) and game.hp == 62


class Backend:
    def __init__(self):
        self.keys = set()
        self.focused = True

    def is_target_focused(self):
        return self.focused

    def key_down(self, key):
        self.keys.add(key)

    def key_up(self, key):
        self.keys.discard(key)


def test_controller_requires_authorization_and_releases_on_emergency():
    backend = Backend()
    with pytest.raises(AuthorizationRequired):
        GuardedController(backend, {})
    controller = GuardedController(backend, {"move_right": "RIGHT"}, authorized=True)
    state = observed()
    action = ActionDecision(
        action=Action.RIGHT,
        reason="test",
        policy="rule",
        confidence=1,
        based_on_frame=0,
        duration_s=0.25,
    )
    errors = []

    def run():
        try:
            controller.perform(action, state)
        except SafetyStop as e:
            errors.append(e)

    thread = threading.Thread(target=run)
    thread.start()
    deadline = time.monotonic() + 1
    while not backend.keys and time.monotonic() < deadline:
        time.sleep(0.001)
    assert backend.keys
    controller.emergency_stop()
    thread.join(1)
    assert not thread.is_alive() and not backend.keys and errors


@pytest.mark.parametrize("failure", ["auth", "focus", "stale", "frame"])
def test_controller_blocks_unsafe_input(failure):
    game = ReferenceArena()
    if failure == "auth":
        game.auth_required = True
    state = observed(game)
    backend = Backend()
    if failure == "focus":
        backend.focused = False
    if failure == "stale":
        state.captured_at -= timedelta(seconds=1)
    action = ActionDecision(
        action=Action.RIGHT,
        reason="test",
        policy="rule",
        confidence=1,
        based_on_frame=1 if failure == "frame" else 0,
    )
    with pytest.raises(SafetyStop):
        GuardedController(backend, {"move_right": "RIGHT"}, authorized=True).perform(action, state)
    assert not backend.keys


def test_model_adapter_has_no_implicit_download_and_validates_choice():
    with pytest.raises(CapabilityUnavailable):
        LayaPolicy()

    class Router:
        def predict(self, state, questions):
            assert "criteria" in questions["action"]
            return {"answers": {"action": {"choice": "attack"}}}

    assert LayaPolicy(Router()).decide(observed()).action == Action.ATTACK
    assert SafeFallbackPolicy().decide(observed()).action == Action.WAIT
