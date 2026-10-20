from uga.core.contracts import Action, GameState


def verify_effect(before: GameState, after: GameState, action: Action) -> bool | None:
    """Confirm observable changes independently of an input backend's delivery result."""
    if action in (Action.LEFT, Action.RIGHT, Action.UP, Action.DOWN):
        if not before.player_position or not after.player_position:
            return None
        p, q = before.player_position.value, after.player_position.value
        if p is None or q is None:
            return None
        return {
            Action.LEFT: q.x < p.x,
            Action.RIGHT: q.x > p.x,
            Action.UP: q.y < p.y,
            Action.DOWN: q.y > p.y,
        }[action]
    if action == Action.ATTACK:
        return len(after.enemies) < len(before.enemies)
    if action == Action.USE_ITEM:
        return len(after.items) < len(before.items)
    return None
