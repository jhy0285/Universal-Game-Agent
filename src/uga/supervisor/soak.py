import json
import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

import psutil

from uga.agents.player.runner import run_episode
from uga.memory.store import atomic_json
from uga.test_game import ArenaConfig


def run_soak(duration_s: float, output: Path, cancel=None, heartbeat=None):
    if not 0 < duration_s <= 57600:
        raise ValueError("soak duration must be in (0, 16 hours]")
    output.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("uga.soak." + str(output.resolve()))
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = RotatingFileHandler(
        output / "episodes.jsonl", maxBytes=10_000_000, backupCount=3, encoding="utf-8"
    )
    logger.addHandler(handler)
    start = time.monotonic()
    process = psutil.Process()
    cpu_start = sum(process.cpu_times()[:2])
    rss = []
    episodes = failures = 0
    try:
        while time.monotonic() - start < duration_s:
            if cancel and cancel.is_set():
                break
            result = run_episode(
                ArenaConfig(seed=(7, 11, 19, 23, 31)[episodes % 5]),
                cancel=cancel,
                heartbeat=heartbeat,
            )
            if result.stop_reason == "cancelled":
                break
            episodes += 1
            failures += not result.success
            rss.append(process.memory_info().rss / 2**20)
            logger.info(json.dumps(result.model_dump(mode="json")))
            atomic_json(
                output / "heartbeat.json",
                {
                    "episodes": episodes,
                    "failures": failures,
                    "elapsed_s": time.monotonic() - start,
                    "rss_mb": rss[-1],
                },
            )
            if not result.success:
                run_episode(ArenaConfig(seed=result.seed), output=output / f"failure-{episodes}")
        summary = {
            "requested_s": duration_s,
            "elapsed_s": time.monotonic() - start,
            "episodes": episodes,
            "failures": failures,
            "cancelled": bool(cancel and cancel.is_set()),
            "passed": episodes > 0 and failures == 0 and not (cancel and cancel.is_set()),
            "rss_peak_mb": max(rss, default=0),
            "rss_growth_after_warmup_mb": rss[-1] - rss[min(2, len(rss) - 1)] if rss else 0,
            "cpu_seconds": sum(process.cpu_times()[:2]) - cpu_start,
        }
        atomic_json(output / "summary.json", summary)
        return summary
    finally:
        logger.removeHandler(handler)
        handler.close()
