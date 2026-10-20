import math
import statistics
from collections import defaultdict

import psutil


def percentile(values: list[float], percent: float) -> float:
    if not values:
        raise ValueError("cannot summarize an empty measurement")
    ordered = sorted(values)
    index = (len(ordered) - 1) * percent / 100
    lo, hi = math.floor(index), math.ceil(index)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo)


class Metrics:
    def __init__(self):
        self.samples = defaultdict(list)
        self.process = psutil.Process()
        self.start_cpu = sum(self.process.cpu_times()[:2])

    def observe(self, name: str, milliseconds: float):
        self.samples[name].append(milliseconds)

    def summarize(self) -> dict[str, float]:
        result = {}
        for name, values in self.samples.items():
            for p in (50, 95, 99):
                result[f"{name}_p{p}_ms"] = percentile(values, p)
            result[f"{name}_mean_ms"] = statistics.mean(values)
        result["rss_mb"] = self.process.memory_info().rss / 2**20
        result["cpu_seconds"] = sum(self.process.cpu_times()[:2]) - self.start_cpu
        return result
