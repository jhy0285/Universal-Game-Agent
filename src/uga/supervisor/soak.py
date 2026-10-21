import hashlib
import json
import logging
import platform
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from uuid import uuid4

import psutil

from uga.agents.player.runner import run_episode
from uga.core.contracts import utcnow
from uga.memory.store import atomic_json
from uga.test_game import ArenaConfig

MILESTONES = (1800, 7200, 14400, 28800, 57600)


def source_fingerprint():
    root = Path(__file__).parents[1]
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def run_soak(
    duration_s: float,
    output: Path,
    cancel=None,
    heartbeat=None,
    *,
    milestones=MILESTONES,
    rss_limit_mb=512,
    growth_limit_mb=64,
):
    if not 0 < duration_s <= 57600:
        raise ValueError("soak duration must be in (0, 16 hours]")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Use a new empty soak output directory to avoid stale results")
    if rss_limit_mb <= 0 or growth_limit_mb < 0:
        raise ValueError("invalid soak memory limits")
    milestones = sorted({float(t) for t in milestones if 0 < t <= duration_s})
    output.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("uga.soak." + str(output.resolve()))
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = RotatingFileHandler(
        output / "episodes.jsonl", maxBytes=10_000_000, backupCount=3, encoding="utf-8"
    )
    logger.addHandler(handler)
    process = psutil.Process()
    run_id = str(uuid4())
    metadata = {
        "run_id": run_id,
        "backend": "reference-pixels-v1",
        "pid": process.pid,
        "create_time": process.create_time(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "source_python_tree_sha256": source_fingerprint(),
        "started_at": utcnow().isoformat(),
        "requested_s": duration_s,
        "rss_limit_mb": rss_limit_mb,
        "growth_limit_mb": growth_limit_mb,
    }
    atomic_json(output / "run.json", {**metadata, "status": "running"})
    rss_peak = rss_now = warmup_rss = 0.0
    episodes = failures = 0
    completed_milestones = []
    failure = None
    latest_metrics = {}

    def snapshot(requested):
        elapsed = time.monotonic() - start
        growth = rss_now - warmup_rss
        cancelled = bool(cancel and cancel.is_set())
        return {
            "run_id": run_id,
            "requested_s": requested,
            "elapsed_s": elapsed,
            "episodes": episodes,
            "failures": failures,
            "cancelled": cancelled,
            "passed": episodes > 0
            and failures == 0
            and not cancelled
            and failure is None
            and elapsed >= requested
            and rss_peak <= rss_limit_mb
            and growth <= growth_limit_mb,
            "rss_peak_mb": rss_peak,
            "rss_growth_after_warmup_mb": growth,
            "cpu_seconds": sum(process.cpu_times()[:2]) - cpu_start,
            "error": failure,
            "latest_episode_metrics": latest_metrics,
            "completed_milestones_s": completed_milestones.copy(),
        }

    # Inventory and initial filesystem writes can be slow on a fresh Windows runner.
    # Measure the requested playback duration after that preparation completes.
    cpu_start = sum(process.cpu_times()[:2])
    start = time.monotonic()
    try:
        while time.monotonic() - start < duration_s:
            if cancel and cancel.is_set():
                break
            result = run_episode(
                ArenaConfig(seed=(7, 11, 19, 23, 31)[episodes % 5]),
                cancel=cancel,
                heartbeat=heartbeat,
                preview_path=output / "last-frame.png",
            )
            if result.stop_reason == "cancelled":
                break
            episodes += 1
            failures += not result.success
            rss_now = process.memory_info().rss / 2**20
            rss_peak = max(rss_peak, rss_now)
            if episodes <= 3:
                warmup_rss = rss_now
            latest_metrics = result.metrics
            logger.info(json.dumps(result.model_dump(mode="json")))
            atomic_json(
                output / "heartbeat.json",
                {
                    "run_id": run_id,
                    "episodes": episodes,
                    "failures": failures,
                    "elapsed_s": time.monotonic() - start,
                    "rss_mb": rss_now,
                    "requested_s": duration_s,
                    "completed_milestones_s": completed_milestones.copy(),
                },
            )
            if not result.success and failures <= 10:
                run_episode(ArenaConfig(seed=result.seed), output=output / f"failure-{episodes}")
            for target in milestones:
                if time.monotonic() - start >= target and target not in completed_milestones:
                    completed_milestones.append(target)
                    atomic_json(output / f"milestone-{target:g}s.json", snapshot(target))
            if rss_peak > rss_limit_mb or rss_now - warmup_rss > growth_limit_mb:
                failure = "memory budget exceeded"
                break
        summary = snapshot(duration_s)
        atomic_json(output / "summary.json", summary)
        atomic_json(
            output / "run.json",
            {
                **metadata,
                "status": "passed"
                if summary["passed"]
                else "cancelled"
                if summary["cancelled"]
                else "failed",
                "finished_at": utcnow().isoformat(),
            },
        )
        return summary
    except BaseException as exc:
        failure = f"{type(exc).__name__}: {exc}"
        atomic_json(output / "summary.json", snapshot(duration_s))
        atomic_json(output / "run.json", {**metadata, "status": "interrupted", "error": failure})
        raise
    finally:
        logger.removeHandler(handler)
        handler.close()
