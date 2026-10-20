import json
import subprocess
import sys
import time
from pathlib import Path

import psutil

from uga.core.errors import UGAError
from uga.memory.store import atomic_json


class FileCancellation:
    def __init__(self, path: Path, event=None):
        self.path, self.event = path, event

    def is_set(self):
        return self.path.is_file() or bool(self.event and self.event.is_set())


class LongRunManager:
    """Own one persisted CPU soak process; progress survives a disconnected terminal."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.manifest = self.root / "process.json"
        self.results = self.root / "results"

    def _read(self, path):
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

    def _owned(self):
        metadata = self._read(self.manifest)
        if not metadata:
            return None
        try:
            process = psutil.Process(metadata["pid"])
            command = process.cmdline()
            if (
                abs(process.create_time() - metadata["create_time"]) < 0.001
                and Path(process.cwd()).resolve() == Path(metadata["cwd"])
                and command
                and Path(command[0]).resolve() == Path(metadata["command"][0]).resolve()
                and command[1:] == metadata["command"][1:]
                and process.status() != psutil.STATUS_ZOMBIE
            ):
                return process
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            pass
        return None

    def status(self):
        process = self._owned()
        run = self._read(self.results / "run.json")
        summary = self._read(self.results / "summary.json")
        heartbeat = self._read(self.results / "heartbeat.json")
        status = run.get("status") if run else "starting" if process else "not_started"
        if not process and status in ("running", "starting"):
            status = "interrupted"
        return {
            "status": status,
            "running": process is not None,
            "pid": process.pid if process else None,
            "run": run,
            "heartbeat": heartbeat,
            "summary": summary,
            "results": str(self.results),
        }

    def start(self, seconds=57600):
        if not 0 < seconds <= 57600:
            raise ValueError("duration must be in (0, 16 hours]")
        if self._owned():
            return self.status()
        if self.root.exists() and any(self.root.iterdir()):
            raise FileExistsError("Use a new long-run output directory")
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / "owner.lock").open("x", encoding="utf-8") as lock:
            lock.write("UGA long-run startup reservation\n")
        command = [
            sys.executable,
            "-m",
            "uga.cli",
            "soak",
            "--seconds",
            str(seconds),
            "--output",
            str(self.results),
        ]
        with (self.root / "console.log").open("ab") as log:
            child = subprocess.Popen(
                command,
                cwd=Path.cwd(),
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=sys.platform != "win32",
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
            )
        process = psutil.Process(child.pid)
        atomic_json(
            self.manifest,
            {
                "pid": child.pid,
                "create_time": process.create_time(),
                "cwd": str(Path.cwd().resolve()),
                "command": command,
            },
        )
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if (self.results / "run.json").is_file():
                return self.status()
            if child.poll() is not None:
                raise UGAError("Soak startup failed; inspect " + str(self.root / "console.log"))
            time.sleep(0.025)
        self.stop()
        raise UGAError("Soak startup deadline exceeded")

    def stop(self):
        process = self._owned()
        if process is not None:
            atomic_json(self.results / "cancel.json", {"cancel": True})
            try:
                process.wait(timeout=5)
            except psutil.TimeoutExpired:
                if self._owned() is not None:
                    process.terminate()
                    try:
                        process.wait(timeout=1)
                    except psutil.TimeoutExpired:
                        if self._owned() is not None:
                            process.kill()
            except psutil.NoSuchProcess:
                pass
        return self.status()
