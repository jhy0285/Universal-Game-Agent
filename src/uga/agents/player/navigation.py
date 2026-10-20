import heapq
import math


def route(start: tuple, goal: tuple, obstacles: list, cell: int = 4) -> tuple | None:
    """A* on the test arena with inflated walls and a deterministic tie break."""
    origin = (round(start[0] / cell), round(start[1] / cell))
    target = (round(goal[0] / cell), round(goal[1] / cell))

    def allowed(p):
        x, y = p[0] * cell, p[1] * cell
        return (
            4 <= x <= 156
            and 16 <= y <= 108
            and not any(a - 3 <= x <= c + 3 and b - 3 <= y <= d + 3 for a, b, c, d in obstacles)
        )

    if not allowed(origin) or not allowed(target):
        return None
    queue = [(0, origin)]
    came = {}
    cost = {origin: 0}
    while queue:
        _, current = heapq.heappop(queue)
        if current == target:
            path = [current]
            while path[-1] in came:
                path.append(came[path[-1]])
            p = path[-2] if len(path) > 1 else path[0]
            return (p[0] * cell, p[1] * cell), (len(path) - 1) * cell
        for p in (
            (current[0] - 1, current[1]),
            (current[0] + 1, current[1]),
            (current[0], current[1] - 1),
            (current[0], current[1] + 1),
        ):
            new = cost[current] + 1
            if allowed(p) and new < cost.get(p, math.inf):
                cost[p] = new
                came[p] = current
                heapq.heappush(queue, (new + abs(target[0] - p[0]) + abs(target[1] - p[1]), p))
    return None


def next_waypoint(start, goal, obstacles, cell=4):
    result = route(start, goal, obstacles, cell)
    return result[0] if result is not None else None


def route_distance(start, goal, obstacles, cell=4):
    result = route(start, goal, obstacles, cell)
    return result[1] if result is not None else math.inf
