import time

from uga.agents.player.perception import Frame, PixelPerception
from uga.core.contracts import utcnow
from uga.model_router.hybrid import HybridPolicy, StrategyPlan, StrategyWorker
from uga.test_game import ReferenceArena


def planner(state):
    time.sleep(0.3)
    return StrategyPlan(
        goal="stop", confidence=1, source_frame=state.frame_id, reason="test handoff"
    )


def test_slow_strategy_does_not_block_fast_control_and_process_is_bounded():
    game = ReferenceArena()
    game.hp = 40
    state = PixelPerception().analyze(Frame(game.render(), 0, utcnow()))
    worker = StrategyWorker(planner, timeout_s=3)
    hybrid = HybridPolicy(strategic=worker)
    try:
        action = hybrid.decide(state)
        assert action.policy == "rule" and worker.process is not None
        assert worker.poll() is None
        deadline = time.monotonic() + 5
        result = None
        while result is None and time.monotonic() < deadline:
            result = worker.poll()
            time.sleep(0.01)
        assert result.goal == "stop"
    finally:
        worker.close()


def test_planner_timeout_terminates_owned_process():
    state = PixelPerception().analyze(Frame(ReferenceArena().render(), 0, utcnow()))
    worker = StrategyWorker(planner, timeout_s=0.01)
    worker.request(state)
    time.sleep(0.02)
    assert worker.poll() is None and worker.process is None
    assert worker.last_error
