import hashlib
from collections import deque
from dataclasses import dataclass
from datetime import datetime

from PIL import Image

from uga.core.contracts import Detection, GameState, Point, utcnow
from uga.core.errors import CapabilityUnavailable
from uga.test_game import AUTH, COMPLETE, ENEMY, GAMEPLAY, HP, ITEM, PLAYER, SIGNATURE, WALL


@dataclass
class Frame:
    image: Image.Image
    frame_id: int
    captured_at: datetime


def components(image: Image.Image, color: tuple) -> list[tuple[int, int, int, int]]:
    pixels = image.load()
    width, height = image.size
    remaining = {(x, y) for y in range(12, height) for x in range(width) if pixels[x, y] == color}
    result = []
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        queue = deque([start])
        points = [start]
        while queue:
            x, y = queue.popleft()
            for p in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if p in remaining:
                    remaining.remove(p)
                    queue.append(p)
                    points.append(p)
        if len(points) >= 9:
            xs, ys = zip(*points, strict=True)
            result.append((min(xs), min(ys), max(xs), max(ys)))
    return result


class PixelPerception:
    """Explicit pixel profile for the UGA test arena, not a general-purpose vision model.

    World ROI segmentation is reused only when the ROI bytes are unchanged. HUD is
    checked on every capture. Unknown games never inherit cached observations.
    """

    def __init__(self):
        self._world_hash = None
        self._world = None
        self.cache_hits = 0

    def analyze(self, frame: Frame) -> GameState:
        image = frame.image.convert("RGB")
        factor = image.width // 160
        if 1 < factor <= 8 and image.size == (160 * factor, 112 * factor):
            image = image.resize((160, 112), Image.Resampling.NEAREST)
        state = GameState(
            frame_id=frame.frame_id,
            captured_at=frame.captured_at,
            frame_sha256=hashlib.sha256(image.tobytes()).hexdigest(),
        )
        if image.size != (160, 112) or image.getpixel((0, 0)) != SIGNATURE:
            return state

        def detect(value):
            return Detection(
                value=value,
                confidence=1,
                source="uga-arena-pixels/v1",
                observed_at=frame.captured_at,
            )

        marker = image.getpixel((4, 0))
        if marker not in (GAMEPLAY, AUTH):
            return state
        state.ui_state = "authentication" if marker == AUTH else "gameplay"
        state.auth_required = detect(marker == AUTH)
        state.goal_complete = detect(image.getpixel((8, 0)) == COMPLETE)
        state.hp = detect(float(sum(image.getpixel((x, 7)) == HP for x in range(10, 110))))
        state.map_id = detect("uga-arena-v1")
        world_hash = hashlib.sha256(image.crop((0, 12, 160, 112)).tobytes()).hexdigest()
        if world_hash == self._world_hash:
            self.cache_hits += 1
            world = self._world
        else:
            world = {
                key: components(image, color)
                for key, color in [
                    ("player", PLAYER),
                    ("enemies", ENEMY),
                    ("items", ITEM),
                    ("obstacles", WALL),
                ]
            }
            self._world, self._world_hash = world, world_hash

        def centers(key):
            return [detect(Point(x=(a + c) / 2, y=(b + d) / 2)) for a, b, c, d in world[key]]

        players = centers("player")
        state.player_position = players[0] if len(players) == 1 else None
        state.enemies = centers("enemies")
        state.items = centers("items")
        state.obstacles = world["obstacles"]
        return state


class MSSCapture:
    def __init__(self, region: dict[str, int]):
        if not all(region.get(k, 0) > 0 for k in ("width", "height")):
            raise ValueError("capture region needs positive width/height")
        try:
            import mss
        except ImportError as exc:
            raise CapabilityUnavailable(
                "Install the capture extra and use a desktop session"
            ) from exc
        self._mss = mss.mss()
        self.region = region
        self.frame_id = 0

    def capture(self) -> Frame:
        raw = self._mss.grab(self.region)
        frame = Frame(Image.frombytes("RGB", raw.size, raw.rgb), self.frame_id, utcnow())
        self.frame_id += 1
        return frame

    def close(self):
        self._mss.close()
