import multiprocessing as mp
import time
from typing import Literal

from pydantic import Field

from uga.agents.player.policies import RuleBasedPolicy, safe_state
from uga.core.contracts import Contract, GameState, utcnow


class StrategyPlan(Contract):
    goal: Literal["fight", "heal", "stop"]
    confidence: float = Field(ge=0, le=1)
    source_frame: int = Field(ge=0)
    reason: str


def _plan(planner, raw, sender):
    try:
        result = StrategyPlan.model_validate(planner(GameState.model_validate(raw)))
        sender.send({"result": result.model_dump(mode="json")})
    except Exception as exc:
        sender.send({"error": str(exc)})
    finally:
        sender.close()


class StrategyWorker:
    """One bounded spawned process. Polling never waits for slow model inference."""

    def __init__(self, planner, timeout_s=2):
        if timeout_s <= 0:
            raise ValueError("planner timeout must be positive")
        self.planner, self.timeout_s = planner, timeout_s
        self.process = self.receiver = None
        self.started = 0
        self.last_error = None

    def request(self, state: GameState):
        if self.process is not None:
            return False
        context = mp.get_context("spawn")
        receiver, sender = context.Pipe(duplex=False)
        self.process = context.Process(
            target=_plan, args=(self.planner, state.model_dump(mode="json"), sender), daemon=True
        )
        self.receiver = receiver
        self.process.start()
        sender.close()
        self.started = time.monotonic()
        return True

    def poll(self):
        if self.process is None:
            return None
        if self.receiver.poll():
            try:
                message = self.receiver.recv()
            except EOFError:
                message = {"error": "planner exited without a result"}
            self.last_error = message.get("error")
            self.close()
            return StrategyPlan.model_validate(message["result"]) if "result" in message else None
        if time.monotonic() - self.started > self.timeout_s or not self.process.is_alive():
            self.last_error = "planner deadline exceeded or process exited"
            self.close()
        return None

    def close(self):
        if self.process is not None:
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(timeout=0.2)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=0.2)
            self.receiver.close()
        self.process = self.receiver = None


class HybridPolicy:
    def __init__(
        self, fast: RuleBasedPolicy | None = None, strategic: StrategyWorker | None = None
    ):
        self.fast = fast or RuleBasedPolicy()
        self.strategic = strategic
        self.plan = None
        self.planned_at = None

    def decide(self, state: GameState):
        if not safe_state(state):
            return self.fast.decide(state)
        if self.strategic:
            new = self.strategic.poll()
            if new and new.confidence >= 0.9 and 0 <= state.frame_id - new.source_frame <= 8:
                self.plan, self.planned_at = new, utcnow()
            unusual = (
                state.hp and state.hp.value is not None and state.hp.value < 60
            ) or not state.enemies
            if unusual:
                self.strategic.request(state)
        goal = (
            self.plan.goal
            if self.plan and (utcnow() - self.planned_at).total_seconds() <= 2
            else None
        )
        return self.fast.decide(state, strategy=goal)
