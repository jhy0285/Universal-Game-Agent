"""Normalize explicitly approved analyzer evidence without inventing game mechanics."""

import hashlib
from pathlib import Path

from uga.agents.reverse.adapters import GhidraAdapter, JadxAdapter, _grant
from uga.agents.reverse.agent import analyze
from uga.core.contracts import Finding, GameSpec
from uga.memory.store import atomic_json


def analyze_with_tool(
    tool: str,
    sample: Path,
    output: Path,
    *,
    approved=False,
    authorized=False,
    trusted_input=False,
    executable: Path | None = None,
    java: Path | None = None,
    installation: Path | None = None,
) -> GameSpec:
    _grant(approved, authorized, trusted_input)
    if tool not in ("jadx", "ghidra"):
        raise ValueError("unsupported analyzer")
    if sample.is_symlink() or not sample.is_file() or sample.stat().st_size > 256_000_000:
        raise ValueError("analysis needs a regular input file of at most 256 MB")
    if output.exists():
        raise FileExistsError(output)
    with sample.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    output.mkdir(parents=True)
    origin = f"{tool}:sha256:{digest}"
    if tool == "jadx":
        evidence = JadxAdapter(executable, java=java, installation=installation).analyze(
            sample, output / "decompiled", approved=True, authorized=True, trusted_input=True
        )
        spec = analyze(output / "decompiled" / "sources", output / "structure", authorized=True)
        for finding in spec.findings:
            finding.source = origin + ":" + finding.source
        spec.name = sample.stem[:100] or "JADX sample"
    else:
        evidence = GhidraAdapter(executable).analyze(
            sample, output / "native", approved=True, authorized=True, trusted_input=True
        )
        functions = evidence["evidence"]["functions"]
        if len(functions) > 100000:
            raise ValueError("function evidence exceeds 100000 entries")
        spec = GameSpec(name=sample.stem[:100] or "Ghidra sample")
        for function in functions:
            if not isinstance(function.get("name"), str) or not isinstance(
                function.get("address"), str
            ):
                raise ValueError("invalid native function evidence")
            calls = function.get("calls", [])
            if not isinstance(calls, list) or not all(isinstance(c, str) for c in calls):
                raise ValueError("invalid native call evidence")
            spec.findings.append(
                Finding(
                    subject=function["name"],
                    statement=f"Ghidra reported function at {function['address']} and {len(calls)} outgoing function references",
                    source=origin + ":" + function["address"],
                    confidence=1,
                )
            )
    spec.requirements.append(
        "Decompiler evidence does not establish gameplay semantics or complete code recovery"
    )
    spec.findings.insert(
        0,
        Finding(
            subject=sample.name,
            statement=f"Authorized input SHA-256 {digest}; target was not executed",
            source=origin,
            confidence=1,
        ),
    )
    atomic_json(
        output / "tool-report.json",
        {
            "tool": tool,
            "target_sha256": digest,
            "executed_target": False,
            "evidence": evidence,
        },
    )
    atomic_json(output / "game-spec.json", spec.model_dump(mode="json"))
    return spec
