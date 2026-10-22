import json
import threading
import time
from pathlib import Path

from pydantic import Field

from uga.agents.player.policies import safe_state
from uga.core.contracts import Action, ActionDecision, Contract, GameState, utcnow
from uga.core.errors import AuthorizationRequired, CapabilityUnavailable, SafetyStop


class MouseDecision(Contract):
    x: int
    y: int
    button: str = Field(default="left", pattern=r"^(left|right)$")
    duration_s: float = Field(default=0.05, gt=0, le=0.25)
    based_on_frame: int = Field(ge=0)


class GuardedController:
    def __init__(
        self, backend, mapping: dict[str, str], *, authorized: bool = False, max_age_s=0.5
    ):
        if not authorized:
            raise AuthorizationRequired("Desktop input requires explicit target authorization")
        self.backend, self.mapping = backend, mapping
        self.max_age_s = max_age_s
        self.stop_event = threading.Event()
        self._lock = threading.RLock()
        self._held = set()
        self._held_mouse = set()

    @classmethod
    def from_config(cls, backend, path: Path, **kwargs):
        return cls(backend, json.loads(path.read_text(encoding="utf-8"))["actions"], **kwargs)

    def release_all(self):
        failures = []
        with self._lock:
            for key in list(self._held):
                try:
                    self.backend.key_up(key)
                    self._held.discard(key)
                except Exception as exc:
                    failures.append(str(exc))
            for button in list(self._held_mouse):
                try:
                    self.backend.mouse_up(button)
                    self._held_mouse.discard(button)
                except Exception as exc:
                    failures.append(str(exc))
        if failures:
            self.stop_event.set()
            raise SafetyStop("input release failed: " + "; ".join(failures))

    def emergency_stop(self):
        self.stop_event.set()
        self.release_all()

    def perform(self, action: ActionDecision, state: GameState) -> bool:
        age = (utcnow() - state.captured_at).total_seconds()
        if (
            self.stop_event.is_set()
            or not safe_state(state)
            or not 0 <= age <= self.max_age_s
            or action.based_on_frame != state.frame_id
            or not self.backend.is_target_focused()
        ):
            self.release_all()
            raise SafetyStop("unsafe state, stale frame, focus loss or emergency stop")
        if action.action == Action.WAIT or action.confidence < 0.6:
            return False
        key = self.mapping.get(action.action.value)
        if key is None:
            raise SafetyStop("action is not allowlisted")
        try:
            with self._lock:
                if self.stop_event.is_set():
                    raise SafetyStop("emergency stop")
                self._held.add(key)
                self.backend.key_down(key)
            deadline = time.monotonic() + action.duration_s
            while time.monotonic() < deadline:
                if (
                    self.stop_event.wait(min(0.01, max(0, deadline - time.monotonic())))
                    or not self.backend.is_target_focused()
                ):
                    raise SafetyStop("interrupted input")
            return True
        finally:
            self.release_all()

    def perform_mouse(self, action: MouseDecision, state: GameState):
        # Reuse the exact state/focus/age gate before moving the pointer.
        self.perform(
            ActionDecision(
                reason="validate mouse scope",
                policy="mouse-guard",
                based_on_frame=action.based_on_frame,
            ),
            state,
        )
        if not self.backend.is_point_in_target(action.x, action.y):
            raise SafetyStop("mouse coordinates are outside the authorized client area")
        try:
            with self._lock:
                if self.stop_event.is_set():
                    raise SafetyStop("emergency stop")
                self.backend.move_mouse(action.x, action.y)
                self._held_mouse.add(action.button)
                self.backend.mouse_down(action.button)
            deadline = time.monotonic() + action.duration_s
            while time.monotonic() < deadline:
                if (
                    self.stop_event.wait(min(0.01, max(0, deadline - time.monotonic())))
                    or not self.backend.is_target_focused()
                ):
                    raise SafetyStop("interrupted mouse input")
            return True
        finally:
            self.release_all()


KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
# Virtual key, set-1 scan code and extended flag. Games that read physical keys (the
# UGA Godot arena uses is_physical_key_pressed) see the scan code, not the virtual key,
# and arrow keys without the extended flag arrive as numeric keypad keys.
WINDOWS_KEYS = {
    "LEFT": (0x25, 0x4B, True),
    "UP": (0x26, 0x48, True),
    "RIGHT": (0x27, 0x4D, True),
    "DOWN": (0x28, 0x50, True),
    "SPACE": (0x20, 0x39, False),
    "Z": (0x5A, 0x2C, False),
    "X": (0x58, 0x2D, False),
}


def keyboard_fields(key: str, up: bool) -> tuple[int, int, int]:
    """KEYBDINPUT wVk, wScan and dwFlags for an allowlisted key."""
    if key not in WINDOWS_KEYS:
        raise SafetyStop("key is not allowlisted")
    vk, scan, extended = WINDOWS_KEYS[key]
    flags = (KEYEVENTF_EXTENDEDKEY if extended else 0) | (KEYEVENTF_KEYUP if up else 0)
    return vk, scan, flags


class WindowsInputBackend:
    """Windows SendInput with foreground PID binding; no game process memory access."""

    def __init__(self, target_pid: int, *, approved: bool = False):
        import sys

        if not approved:
            raise AuthorizationRequired("Pass explicit desktop-input approval")
        if sys.platform != "win32":
            raise CapabilityUnavailable("Windows SendInput requires Windows 11 desktop")
        if target_pid <= 0:
            raise ValueError("target PID must be positive")
        import ctypes
        from ctypes import wintypes as w

        self.ctypes, self.w, self.pid = ctypes, w, target_pid
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)

        class Mouse(ctypes.Structure):
            _fields_ = [
                ("dx", w.LONG),
                ("dy", w.LONG),
                ("mouseData", w.DWORD),
                ("dwFlags", w.DWORD),
                ("time", w.DWORD),
                ("dwExtraInfo", w.WPARAM),
            ]

        class Keyboard(ctypes.Structure):
            _fields_ = [
                ("wVk", w.WORD),
                ("wScan", w.WORD),
                ("dwFlags", w.DWORD),
                ("time", w.DWORD),
                ("dwExtraInfo", w.WPARAM),
            ]

        class Hardware(ctypes.Structure):
            _fields_ = [("uMsg", w.DWORD), ("wParamL", w.WORD), ("wParamH", w.WORD)]

        class Union(ctypes.Union):
            _fields_ = [("mi", Mouse), ("ki", Keyboard), ("hi", Hardware)]

        class Input(ctypes.Structure):
            _anonymous_ = ("value",)
            _fields_ = [("type", w.DWORD), ("value", Union)]

        self.Input, self.Keyboard, self.Mouse = Input, Keyboard, Mouse
        self.user32.SendInput.argtypes = [w.UINT, ctypes.POINTER(Input), ctypes.c_int]
        self.user32.SendInput.restype = w.UINT
        self.user32.GetForegroundWindow.restype = w.HWND
        self.user32.GetForegroundWindow.argtypes = []
        self.user32.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
        self.user32.GetWindowThreadProcessId.restype = w.DWORD
        self.user32.GetClientRect.argtypes = [w.HWND, ctypes.POINTER(w.RECT)]
        self.user32.GetClientRect.restype = w.BOOL
        self.user32.ClientToScreen.argtypes = [w.HWND, ctypes.POINTER(w.POINT)]
        self.user32.ClientToScreen.restype = w.BOOL
        self.user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]

    def is_target_focused(self):
        pid = self.w.DWORD()
        self.user32.GetWindowThreadProcessId(
            self.user32.GetForegroundWindow(), self.ctypes.byref(pid)
        )
        return pid.value == self.pid

    def client_region(self):
        """Physical client bounds, after MSS has initialized Windows DPI awareness."""
        window = self.user32.GetForegroundWindow()
        pid = self.w.DWORD()
        self.user32.GetWindowThreadProcessId(window, self.ctypes.byref(pid))
        if not window or pid.value != self.pid:
            raise SafetyStop("Focus the authorized game window before capturing")
        rectangle, origin = self.w.RECT(), self.w.POINT(0, 0)
        if not self.user32.GetClientRect(
            window, self.ctypes.byref(rectangle)
        ) or not self.user32.ClientToScreen(window, self.ctypes.byref(origin)):
            raise OSError(self.ctypes.get_last_error(), "Cannot read game client bounds")
        width, height = rectangle.right - rectangle.left, rectangle.bottom - rectangle.top
        if width <= 0 or height <= 0 or not self.is_target_focused():
            raise SafetyStop("Game window has no visible client area or lost focus")
        return {"left": origin.x, "top": origin.y, "width": width, "height": height}

    def _key(self, key, up):
        fields = keyboard_fields(key, up)
        if not up and not self.is_target_focused():
            raise SafetyStop("target lost focus")
        event = self.Input(type=1, ki=self.Keyboard(*fields, 0, 0))
        if self.user32.SendInput(1, self.ctypes.byref(event), self.ctypes.sizeof(event)) != 1:
            raise OSError(self.ctypes.get_last_error(), "SendInput failed")

    def key_down(self, key):
        self._key(key, False)

    def key_up(self, key):
        self._key(key, True)

    def is_point_in_target(self, x, y):
        if not self.is_target_focused():
            return False
        window = self.user32.GetForegroundWindow()
        rectangle = self.w.RECT()
        origin = self.w.POINT(0, 0)
        if not self.user32.GetClientRect(
            window, self.ctypes.byref(rectangle)
        ) or not self.user32.ClientToScreen(window, self.ctypes.byref(origin)):
            return False
        return (
            origin.x <= x < origin.x + rectangle.right
            and origin.y <= y < origin.y + rectangle.bottom
        )

    def move_mouse(self, x, y):
        if not self.is_point_in_target(x, y):
            raise SafetyStop("mouse point is outside authorized window")
        if not self.user32.SetCursorPos(x, y):
            raise OSError("SetCursorPos failed")

    def _mouse(self, button, up):
        flags = {"left": (2, 4), "right": (8, 16)}
        if button not in flags:
            raise SafetyStop("mouse button is not allowlisted")
        if not up and not self.is_target_focused():
            raise SafetyStop("target lost focus")
        event = self.Input(type=0, mi=self.Mouse(0, 0, 0, flags[button][int(up)], 0, 0))
        if self.user32.SendInput(1, self.ctypes.byref(event), self.ctypes.sizeof(event)) != 1:
            raise OSError(self.ctypes.get_last_error(), "mouse SendInput failed")

    def mouse_down(self, button):
        self._mouse(button, False)

    def mouse_up(self, button):
        self._mouse(button, True)
