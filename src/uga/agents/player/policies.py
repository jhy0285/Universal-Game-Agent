import json
import math
from typing import Protocol

from uga.agents.player.navigation import next_waypoint, route_distance
from uga.core.contracts import Action, ActionDecision, GameState
from uga.core.errors import CapabilityUnavailable


class Policy(Protocol):
    def decide(self, state: GameState) -> ActionDecision: ...


def decision(
    state, action=Action.WAIT, reason="unknown observation", policy="fallback", confidence=0
):
    return ActionDecision(
        action=action,
        reason=reason,
        policy=policy,
        confidence=confidence,
        based_on_frame=state.frame_id,
    )


def safe_state(state: GameState) -> bool:
    return (
        state.ui_state == "gameplay"
        and state.auth_required is not None
        and state.auth_required.value is False
        and state.auth_required.confidence >= 0.9
        and state.player_position is not None
        and state.player_position.value is not None
        and state.player_position.confidence >= 0.9
    )


class SafeFallbackPolicy:
    def decide(self, state):
        return decision(state, reason="stop: unknown, unsafe or unsupported state")


class RuleBasedPolicy:
    def __init__(self, attack_range: float = 14, navigation_mode: str = "euclidean"):
        if not math.isfinite(attack_range) or not 1 <= attack_range <= 20:
            raise ValueError("attack range must be finite and in [1,20]")
        self.attack_range = attack_range
        if navigation_mode not in ("euclidean", "geodesic"):
            raise ValueError("unsupported navigation mode")
        self.navigation_mode = navigation_mode
        self._target_key = self._target = None

    def decide(self, state, strategy=None):
        if not safe_state(state):
            return SafeFallbackPolicy().decide(state)
        if state.goal_complete and state.goal_complete.value:
            return decision(state, reason="goal complete", policy="rule", confidence=1)
        if strategy == "stop":
            return decision(state, reason="strategic human handoff", policy="rule", confidence=1)
        p = state.player_position.value
        start = (p.x, p.y)
        healing = bool(
            state.hp
            and state.hp.value is not None
            and (state.hp.value < 60 or strategy == "heal")
            and state.items
        )
        candidates = state.items if healing else state.enemies
        targets = [d.value for d in candidates if d.value is not None and d.confidence >= 0.9]
        if not targets:
            return decision(state, reason="no reliable target", policy="rule")
        if self.navigation_mode == "geodesic":
            # Re-rank after world/target changes, not every control tick.
            key = (healing, tuple((t.x, t.y) for t in targets), tuple(state.obstacles))
            if key != self._target_key:
                self._target = min(
                    targets, key=lambda t: route_distance(start, (t.x, t.y), state.obstacles)
                )
                self._target_key = key
            target = self._target
        else:
            target = min(targets, key=lambda t: math.dist(start, (t.x, t.y)))
        distance = math.dist(start, (target.x, target.y))
        if distance <= (10 if healing else self.attack_range):
            return decision(
                state, Action.USE_ITEM if healing else Action.ATTACK, "target in range", "rule", 1
            )
        waypoint = next_waypoint(start, (target.x, target.y), state.obstacles)
        if waypoint is None:
            return decision(state, reason="no collision-free route", policy="rule")
        dx, dy = waypoint[0] - p.x, waypoint[1] - p.y
        action = (
            (Action.RIGHT if dx > 0 else Action.LEFT)
            if abs(dx) >= abs(dy)
            else (Action.DOWN if dy > 0 else Action.UP)
        )
        return decision(state, action, "A* waypoint", "rule", 1)


class LayaPolicy:
    """Adapter for the verified Router.predict API; caller owns model installation/loading.

    A Router is explicitly injected: constructing this adapter never downloads weights.
    This is a text-state decision engine, not an image perception model.
    """

    def __init__(self, router=None):
        if router is None:
            raise CapabilityUnavailable(
                "Install/verify local Laya weights and inject laya.Router; no implicit downloads"
            )
        self.router = router

    def decide(self, state):
        if not safe_state(state):
            return SafeFallbackPolicy().decide(state)
        result = self.router.predict(
            state.model_dump_json(),
            {
                "action": {
                    "type": "choice",
                    "instructions": "Choose one allowed action for the authorized test arena.",
                    "criteria": {a.value: a.value.replace("_", " ") for a in Action},
                }
            },
        )
        try:
            choice = Action(result["answers"]["action"]["choice"])
        except (KeyError, ValueError, TypeError):
            return decision(state, reason="invalid Laya result")
        # Upstream confidence is not assumed calibrated for games.
        return decision(state, choice, "Laya typed choice (uncalibrated)", "laya", 0.5)


class LLMPolicy:
    """Provider-neutral injected callable, no external AI connection by default."""

    def __init__(self, predict=None):
        if predict is None:
            raise CapabilityUnavailable("No LLM provider configured")
        self.predict = predict

    def decide(self, state):
        if not safe_state(state):
            return SafeFallbackPolicy().decide(state)
        try:
            response = self.predict(state.model_dump(mode="json"))
            result = ActionDecision.model_validate(
                json.loads(response) if isinstance(response, str) else response
            )
            if result.based_on_frame != state.frame_id:
                return decision(state, reason="provider returned stale decision")
            return result
        except (ValueError, TypeError):
            return decision(state, reason="invalid provider result")


class VLMPolicy(LLMPolicy):
    """Same decision contract; a provider must explicitly combine pixels and observations."""
