import http.client
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import psutil

from uga.core.errors import UGAError
from uga.memory.store import atomic_json


class ServiceManager:
    """Restartable local server; signal only the process identity created by this manager."""

    def __init__(self, root: Path, workspace: Path | None = None):
        self.root = root.resolve()
        self.workspace = (workspace or Path.cwd()).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.metadata = self.root / "service.json"

    def _owned(self):
        if not self.metadata.is_file():
            return None
        value = json.loads(self.metadata.read_text(encoding="utf-8"))
        try:
            process = psutil.Process(value["pid"])
            if (
                abs(process.create_time() - value["created"]) > 0.001
                or not process.is_running()
                or process.status() == psutil.STATUS_ZOMBIE
            ):
                return None
            command = process.cmdline()
            if (
                command[1:4] != ["-m", "uga.cli", "serve"]
                or Path(process.cwd()).resolve() != self.workspace
            ):
                raise UGAError("service PID is not an owned UGA server; refusing to signal it")
            return process, value
        except psutil.NoSuchProcess:
            return None

    def status(self):
        owned = self._owned()
        if not owned:
            return {"running": False, "healthy": False}
        process, value = owned
        healthy = False
        connection = http.client.HTTPConnection("127.0.0.1", value["port"], timeout=1)
        try:
            connection.request("GET", "/health")
            response = connection.getresponse()
            healthy = (
                response.status == 200 and json.loads(response.read(4096)).get("status") == "ok"
            )
        except (OSError, ValueError, http.client.HTTPException):
            pass
        finally:
            connection.close()
        result = {"running": True, "healthy": healthy, "pid": process.pid, "port": value["port"]}
        token = self.root / "api-token"
        if healthy and token.is_file():
            # The fragment stays in the browser; the dashboard HTML itself carries no token.
            result["dashboard_url"] = (
                f"http://127.0.0.1:{value['port']}/#token={token.read_text(encoding='utf-8')}"
            )
        return result

    def start(self, port=8765):
        if not 1024 <= port <= 65535:
            raise ValueError("service port must be 1024..65535")
        current = self.status()
        if current["running"]:
            if current["port"] != port:
                raise UGAError("state directory already owns a server on a different port")
            return {**current, "reused": True}
        command = [
            sys.executable,
            "-m",
            "uga.cli",
            "serve",
            "--port",
            str(port),
            "--state-dir",
            str(self.root),
            "--analysis-root",
            str(self.workspace),
        ]
        with (self.root / "server.log").open("ab") as log:
            process = subprocess.Popen(
                command,
                cwd=self.workspace,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=os.name != "nt",
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )
        try:
            atomic_json(
                self.metadata,
                {
                    "pid": process.pid,
                    "created": psutil.Process(process.pid).create_time(),
                    "port": port,
                },
            )
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline and process.poll() is None:
                current = self.status()
                if current["healthy"]:
                    return {**current, "reused": False}
                time.sleep(0.1)
            raise UGAError("server did not become healthy; inspect state directory server.log")
        except BaseException:
            self.stop()
            raise

    def stop(self):
        owned = self._owned()
        if not owned:
            return {"stopped": False, "reason": "no owned live server"}
        process, value = owned
        children = process.children(recursive=True)
        if os.name == "nt":
            process.terminate()
        else:
            process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except psutil.TimeoutExpired:
            process.kill()
        for child in children:
            try:
                if child.is_running():
                    child.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(children, timeout=0.5)
        for child in alive:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        return {"stopped": True, "pid": value["pid"]}
