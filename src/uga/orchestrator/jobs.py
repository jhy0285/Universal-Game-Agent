import multiprocessing as mp
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import psutil

from uga.core.contracts import AgentEvent, TaskSpec, TaskStatus
from uga.core.errors import UGAError
from uga.memory.store import Store
from uga.orchestrator.worker import execute_task, validate_task
from uga.supervisor.health import Watchdog


@dataclass
class Running:
    spec: TaskSpec
    process: object
    receiver: object
    started: float
    watchdog: Watchdog


class Orchestrator:
    def __init__(
        self,
        root: Path,
        *,
        analysis_root: Path | None = None,
        max_workers=2,
        max_queue=32,
        heartbeat_timeout_s=10,
        memory_limit_mb=512,
        recovery_limit=1,
    ):
        if not 1 <= max_workers <= 4 or not 1 <= max_queue <= 100:
            raise ValueError("invalid worker/queue limits")
        if not 0 <= recovery_limit <= 2:
            raise ValueError("invalid recovery limit")
        self.store = Store(root)
        self.root = self.store.root
        self.analysis_root = (analysis_root or Path.cwd()).resolve()
        self.max_workers, self.max_queue = max_workers, max_queue
        self.heartbeat_timeout_s, self.memory_limit_mb = heartbeat_timeout_s, memory_limit_mb
        self.recovery_limit = recovery_limit
        self.context = mp.get_context("spawn")
        self.pending = deque()
        self.running = {}
        self.attempts = {}
        self.started = {}
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self.lock_path = self.root / "orchestrator.lock"
        self._acquire()
        for row in self.store.tasks(limit=100000):
            if row["status"] in (TaskStatus.QUEUED, TaskStatus.RUNNING):
                self.store.update_task(
                    row["id"],
                    TaskStatus.FAILED,
                    error="interrupted by previous process shutdown; resubmit explicitly",
                )
        self.thread = threading.Thread(target=self._monitor, daemon=True, name="uga-job-monitor")
        self.thread.start()

    def _acquire(self):
        self._owner = self.lock_path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt

                self._owner.seek(0)
                if not self._owner.read(1):
                    self._owner.write(b"0")
                    self._owner.flush()
                self._owner.seek(0)
                msvcrt.locking(self._owner.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._owner.close()
            raise UGAError("an orchestrator already owns this state directory") from None

    def _event(self, spec, event, message, level="info", **data):
        self.store.append_event(
            AgentEvent(
                task_id=spec.task_id,
                agent=spec.agent,
                event=event,
                message=message,
                level=level,
                data=data,
            )
        )

    def submit(self, spec: TaskSpec):
        spec = spec.model_copy(deep=True)
        if (
            spec.agent == "player"
            and spec.operation == "play"
            and "attack_range" not in spec.parameters
        ):
            active = self.store.load_checkpoint("active-policy")
            if active:
                spec.parameters["attack_range"] = active["attack_range"]
                spec.parameters.setdefault(
                    "navigation_mode", active.get("navigation_mode", "euclidean")
                )
        validate_task(spec)
        with self._lock:
            if self._stop.is_set():
                raise UGAError("orchestrator is closed")
            if len(self.pending) >= self.max_queue:
                raise UGAError("job queue is full")
            self.store.create_task(spec)
            self.pending.append(spec)
            self._event(spec, "queued", "job accepted")
        return self.store.task(spec.task_id)

    def _launch(self, spec):
        receiver, sender = self.context.Pipe(duplex=False)
        process = self.context.Process(
            target=execute_task,
            args=(spec.model_dump(mode="json"), str(self.root), str(self.analysis_root), sender),
            daemon=False,
        )
        process.start()
        sender.close()
        watchdog = Watchdog(self.heartbeat_timeout_s, self.memory_limit_mb)
        watchdog.register("inference" if spec.agent == "player" else "worker", process.pid)
        started = self.started.setdefault(spec.task_id, time.monotonic())
        self.running[spec.task_id] = Running(spec, process, receiver, started, watchdog)
        self.store.update_task(spec.task_id, TaskStatus.RUNNING)
        self._event(
            spec,
            "started",
            "isolated worker started",
            pid=process.pid,
            attempt=self.attempts.get(spec.task_id, 0),
        )

    def _terminate(self, run):
        if run.process.is_alive():
            try:
                process = psutil.Process(run.process.pid)
                descendants = process.children(recursive=True)
                for child in descendants:
                    try:
                        child.terminate()
                    except psutil.NoSuchProcess:
                        pass
                run.process.terminate()
                _, alive = psutil.wait_procs(descendants, timeout=0.3)
                for child in alive:
                    try:
                        child.kill()
                    except psutil.NoSuchProcess:
                        pass
            except psutil.NoSuchProcess:
                pass
        run.process.join(timeout=0.5)
        if run.process.is_alive():
            run.process.kill()
            run.process.join(timeout=0.5)
        run.receiver.close()

    def _finish(self, run, status, result=None, error=None):
        self._terminate(run)
        self.running.pop(run.spec.task_id, None)
        self.store.update_task(run.spec.task_id, status, result, error)
        self._event(
            run.spec,
            status.value,
            error or "job completed",
            level="error" if status == TaskStatus.FAILED else "info",
        )

    def _tick(self):
        for task_id, run in list(self.running.items()):
            finished = False
            while run.receiver.poll():
                try:
                    message = run.receiver.recv()
                except EOFError:
                    break
                if message["type"] == "heartbeat":
                    role = next(iter(run.watchdog.processes))
                    run.watchdog.heartbeat(role)
                    self.store.checkpoint(
                        task_id, {"tick": message["tick"], "pid": run.process.pid}
                    )
                elif message["type"] == "result":
                    self._finish(run, TaskStatus.SUCCEEDED, result=message["result"])
                    finished = True
                    break
                elif message["type"] == "error":
                    self._finish(run, TaskStatus.FAILED, error=message["error"])
                    finished = True
                    break
            if finished:
                continue
            if time.monotonic() - run.started > run.spec.timeout_s:
                self._finish(run, TaskStatus.TIMED_OUT, error="task deadline exceeded")
                continue
            health = next(iter(run.watchdog.inspect().values()))
            if not health["healthy"] or not run.process.is_alive():
                reason = health["reason"] or "worker exited without result"
                attempts = self.attempts.get(task_id, 0)
                # Recovery is restricted to idempotent reference playback; never repeat external effects.
                if (
                    reason in ("process_exited", "process_unavailable", "heartbeat_timeout")
                    and run.spec.operation == "play"
                    and attempts < self.recovery_limit
                ):
                    self._terminate(run)
                    self.running.pop(task_id, None)
                    self.attempts[task_id] = attempts + 1
                    self._event(run.spec, "recovering", reason, level="warning")
                    self._launch(run.spec)
                else:
                    self._finish(run, TaskStatus.FAILED, error=reason)
        while self.pending and len(self.running) < self.max_workers:
            spec = self.pending.popleft()
            try:
                self._launch(spec)
            except Exception as exc:
                self.store.update_task(
                    spec.task_id, TaskStatus.FAILED, error=f"worker startup: {exc}"
                )

    def _monitor(self):
        while not self._stop.wait(0.05):
            try:
                with self._lock:
                    self._tick()
            except Exception as exc:
                self.store.checkpoint("monitor-error", {"error": str(exc)})
                self._stop.set()

    def cancel(self, task_id):
        with self._lock:
            for spec in list(self.pending):
                if spec.task_id == task_id:
                    self.pending.remove(spec)
                    self.store.update_task(task_id, TaskStatus.CANCELLED)
                    self._event(spec, "cancelled", "queued job cancelled")
                    return self.store.task(task_id)
            if task_id in self.running:
                self._finish(self.running[task_id], TaskStatus.CANCELLED, error="cancelled by user")
            return self.store.task(task_id)

    def close(self):
        self._stop.set()
        self.thread.join(timeout=2)
        with self._lock:
            for task_id in list(self.running):
                self.cancel(task_id)
            for spec in list(self.pending):
                self.cancel(spec.task_id)
            self._owner.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
