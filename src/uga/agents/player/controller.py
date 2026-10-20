import json
import threading
import time
from pathlib import Path

from uga.agents.player.policies import safe_state
from uga.core.contracts import Action, ActionDecision, GameState, utcnow
from uga.core.errors import AuthorizationRequired, CapabilityUnavailable, SafetyStop


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

    @classmethod
    def from_config(cls, backend, path: Path, **kwargs):
        return cls(backend, json.loads(path.read_text(encoding="utf-8"))["actions"], **kwargs)

    def release_all(self):
        with self._lock:
            for key in list(self._held):
                self.backend.key_up(key)
                self._held.discard(key)

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


class WindowsInputBackend:
    """Windows SendInput with foreground PID binding; no game process memory access."""

    VK = {
        "LEFT": 0x25,
        "UP": 0x26,
        "RIGHT": 0x27,
        "DOWN": 0x28,
        "SPACE": 0x20,
        "Z": 0x5A,
        "X": 0x58,
    }

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

        self.Input, self.Keyboard = Input, Keyboard
        self.user32.SendInput.argtypes = [w.UINT, ctypes.POINTER(Input), ctypes.c_int]
        self.user32.SendInput.restype = w.UINT
        self.user32.GetForegroundWindow.restype = w.HWND
        self.user32.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]

    def is_target_focused(self):
        pid = self.w.DWORD()
        self.user32.GetWindowThreadProcessId(
            self.user32.GetForegroundWindow(), self.ctypes.byref(pid)
        )
        return pid.value == self.pid

    def _key(self, key, up):
        if key not in self.VK:
            raise SafetyStop("key is not allowlisted")
        if not up and not self.is_target_focused():
            raise SafetyStop("target lost focus")
        event = self.Input(type=1, ki=self.Keyboard(self.VK[key], 0, 2 if up else 0, 0, 0))
        if self.user32.SendInput(1, self.ctypes.byref(event), self.ctypes.sizeof(event)) != 1:
            raise OSError(self.ctypes.get_last_error(), "SendInput failed")

    def key_down(self, key):
        self._key(key, False)

    def key_up(self, key):
        self._key(key, True)
