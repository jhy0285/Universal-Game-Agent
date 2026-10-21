import os
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import psutil

from uga.core.errors import AuthorizationRequired, UGAError


@dataclass
class ToolResult:
    command: list[str]
    returncode: int
    output: str
    elapsed_s: float
    resources: dict[str, float] = field(default_factory=dict)


def terminate_owned(process, observed_children=()):
    try:
        children = psutil.Process(process.pid).children(recursive=True)
    except psutil.NoSuchProcess:
        children = []
    children = list({child.pid: child for child in [*observed_children, *children]}.values())
    for child in reversed(children):
        try:
            child.terminate()
        except psutil.NoSuchProcess:
            pass
    if os.name != "nt":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        process.wait(timeout=2)
    _, alive = psutil.wait_procs(children, timeout=0.2)
    for child in alive:
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass


def run_tool(
    command: list[str],
    cwd: Path,
    *,
    approved: bool = False,
    timeout_s=60,
    max_output_bytes=2_000_000,
    max_rss_mb=512,
    driver=None,
) -> ToolResult:
    if not command:
        raise ValueError("use an absolute executable path")
    if not approved:
        raise AuthorizationRequired(
            f"External tool execution needs approval: {Path(command[0]).name}"
        )
    if not command or not Path(command[0]).is_absolute():
        raise ValueError("use an absolute executable path")
    if timeout_s <= 0 or max_output_bytes < 1 or max_rss_mb <= 0:
        raise ValueError("tool time, output and memory budgets must be positive")
    if os.name == "nt" and Path(command[0]).suffix.lower() in (".bat", ".cmd"):
        raise UGAError(
            "Use a direct executable launcher on Windows; batch argument escaping is not supported"
        )
    cwd = cwd.resolve()
    start = time.monotonic()
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            shell=False,
            start_new_session=os.name != "nt",
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
        sampled_rss = sampled_cpu = 0.0
        observed = {}
        cpu_samples = {}
        last_resource_check = 0.0
        try:
            while process.poll() is None:
                if time.monotonic() - start > timeout_s:
                    raise TimeoutError("external tool deadline exceeded")
                if log.tell() > max_output_bytes:
                    raise UGAError("external tool exceeded output limit")
                if time.monotonic() - last_resource_check >= 0.05:
                    last_resource_check = time.monotonic()
                    try:
                        child = psutil.Process(process.pid)
                        tree = [child, *child.children(recursive=True)]
                        if len(tree) > 32:
                            raise UGAError("external tool exceeded process count limit")
                        rss = 0.0
                        for member in tree:
                            try:
                                identity = (member.pid, member.create_time())
                                observed[identity] = member
                                if len(observed) > 256:
                                    raise UGAError("external tool exceeded lifetime process limit")
                                rss += member.memory_info().rss / 2**20
                                cpu_samples[identity] = max(
                                    cpu_samples.get(identity, 0), sum(member.cpu_times()[:2])
                                )
                            except psutil.NoSuchProcess:
                                continue
                        sampled_rss = max(sampled_rss, rss)
                        sampled_cpu = sum(cpu_samples.values())
                        if rss > max_rss_mb:
                            raise UGAError("external tool exceeded memory limit")
                    except psutil.NoSuchProcess:
                        pass
                if driver:
                    driver()
                time.sleep(0.005)
            log.seek(0)
            log.seek(0, 2)
            if log.tell() > max_output_bytes:
                raise UGAError("external tool exceeded output limit")
            log.seek(0)
            output = log.read(max_output_bytes).decode("utf-8", "replace")
            result = ToolResult(
                command,
                process.returncode,
                output,
                time.monotonic() - start,
                {"sampled_peak_rss_mb": sampled_rss, "sampled_cpu_seconds": sampled_cpu},
            )
            if result.returncode != 0:
                raise UGAError(
                    f"{Path(command[0]).name} exited {result.returncode}: {output[-4000:]}"
                )
            return result
        finally:
            terminate_owned(
                process, [member for member in observed.values() if member.pid != process.pid]
            )
