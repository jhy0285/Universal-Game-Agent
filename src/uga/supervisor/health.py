import time
from dataclasses import dataclass, field

import psutil


@dataclass
class ProcessHealth:
    role: str
    pid: int
    create_time: float
    heartbeat_at: float = field(default_factory=time.monotonic)
    started_at: float = field(default_factory=time.monotonic)


class Watchdog:
    """Observe game/inference/worker processes independently; never signal foreign PIDs."""

    def __init__(self, heartbeat_timeout_s=10, memory_limit_mb=512):
        self.heartbeat_timeout_s = heartbeat_timeout_s
        self.memory_limit_mb = memory_limit_mb
        self.processes = {}

    def register(self, role: str, pid: int):
        process = psutil.Process(pid)
        self.processes[role] = ProcessHealth(role, pid, process.create_time())

    def heartbeat(self, role: str, now=None):
        self.processes[role].heartbeat_at = time.monotonic() if now is None else now

    def inspect(self, now=None):
        now = time.monotonic() if now is None else now
        result = {}
        for role, health in self.processes.items():
            try:
                process = psutil.Process(health.pid)
                if (
                    abs(process.create_time() - health.create_time) > 0.001
                    or not process.is_running()
                    or process.status() == psutil.STATUS_ZOMBIE
                ):
                    result[role] = {"healthy": False, "reason": "process_exited"}
                    continue
                rss = process.memory_info().rss / 2**20
                reason = (
                    "memory_limit"
                    if rss > self.memory_limit_mb
                    else "heartbeat_timeout"
                    if now - health.heartbeat_at > self.heartbeat_timeout_s
                    else None
                )
                result[role] = {
                    "healthy": reason is None,
                    "reason": reason,
                    "rss_mb": rss,
                    "heartbeat_age_s": max(0, now - health.heartbeat_at),
                }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                result[role] = {"healthy": False, "reason": "process_unavailable"}
        return result
