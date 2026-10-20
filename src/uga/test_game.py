"""Deterministic CPU reference arena. This is not the Godot runtime."""

import math
import random

from PIL import Image, ImageDraw
from pydantic import Field

from uga.core.contracts import Action, Contract

BACKGROUND = (18, 22, 35)
PLAYER = (70, 160, 250)
ENEMY = (240, 70, 90)
ITEM = (80, 220, 130)
WALL = (110, 115, 135)
SIGNATURE = (10, 220, 230)
GAMEPLAY = (20, 200, 80)
AUTH = (255, 180, 0)
COMPLETE = (180, 100, 255)
HP = (240, 60, 60)


class ArenaConfig(Contract):
    seed: int = 7
    enemy_count: int = Field(default=3, ge=1, le=8)
    speed: int = Field(default=4, ge=1, le=8)
    attack_range: int = Field(default=14, ge=8, le=20)
    obstacles: bool = True
    max_steps: int = Field(default=600, ge=1, le=100000)


class ReferenceArena:
    width, height = 160, 112

    def __init__(self, config: ArenaConfig | None = None):
        self.config = config or ArenaConfig()
        rng = random.Random(self.config.seed)
        self.player = [20, 56]
        choices = [(x, y) for x in (108, 124, 144) for y in (20, 40, 64, 88, 104)]
        self.enemies = [list(p) for p in rng.sample(choices, self.config.enemy_count)]
        self.items = [[28, 92]]
        self.obstacles = [(72, 28, 80, 80)] if self.config.obstacles else []
        self.hp, self.tick, self.auth_required = 100, 0, False
        self.last_effect = False

    @property
    def won(self) -> bool:
        return not self.enemies and self.hp > 0

    @property
    def done(self) -> bool:
        return self.won or self.hp <= 0 or self.tick >= self.config.max_steps

    def step(self, action: Action) -> bool:
        self.last_effect = False
        if self.done or self.auth_required:
            return False
        self.tick += 1
        offsets = {
            Action.LEFT: (-1, 0),
            Action.RIGHT: (1, 0),
            Action.UP: (0, -1),
            Action.DOWN: (0, 1),
        }
        if action in offsets:
            dx, dy = offsets[action]
            x = self.player[0] + dx * self.config.speed
            y = self.player[1] + dy * self.config.speed
            blocked = any(
                a - 2 <= x <= c + 2 and b - 2 <= y <= d + 2 for a, b, c, d in self.obstacles
            )
            if 4 <= x <= self.width - 4 and 16 <= y <= self.height - 4 and not blocked:
                self.player = [x, y]
                self.last_effect = True
        elif action == Action.ATTACK:
            target = next(
                (e for e in self.enemies if math.dist(e, self.player) <= self.config.attack_range),
                None,
            )
            if target is not None:
                self.enemies.remove(target)
                self.last_effect = True
        elif action == Action.USE_ITEM:
            target = next((i for i in self.items if math.dist(i, self.player) <= 10), None)
            if target is not None:
                self.items.remove(target)
                self.hp = min(100, self.hp + 30)
                self.last_effect = True
        elif action == Action.JUMP:
            self.last_effect = True
        if self.tick % 5 == 0 and action != Action.JUMP:
            self.hp = max(
                0, self.hp - 6 * sum(math.dist(e, self.player) < 11 for e in self.enemies)
            )
        return self.last_effect

    def render(self) -> Image.Image:
        image = Image.new("RGB", (self.width, self.height), BACKGROUND)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 3, 3), fill=SIGNATURE)
        draw.rectangle((4, 0, 7, 3), fill=AUTH if self.auth_required else GAMEPLAY)
        if self.won:
            draw.rectangle((8, 0, 11, 3), fill=COMPLETE)
        if self.hp:
            draw.rectangle((10, 6, 9 + self.hp, 8), fill=HP)
        for rect in self.obstacles:
            draw.rectangle(rect, fill=WALL)
        for positions, color in [
            (self.items, ITEM),
            (self.enemies, ENEMY),
            ([self.player], PLAYER),
        ]:
            for x, y in positions:
                draw.rectangle((x - 2, y - 2, x + 2, y + 2), fill=color)
        return image

    def truth(self) -> dict:
        return {
            "player": list(self.player),
            "hp": self.hp,
            "enemies": len(self.enemies),
            "tick": self.tick,
            "won": self.won,
            "auth_required": self.auth_required,
        }
