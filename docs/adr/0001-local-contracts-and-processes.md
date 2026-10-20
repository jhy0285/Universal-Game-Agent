# ADR 0001: CPU-first, versioned contracts and process isolation

Status: accepted. Date: 2026-10-20.

The repository is empty (no commits or source files). Build a new Python package rather
than infer dependencies from the repository name. Use Python >=3.11, Pydantic v2,
FastAPI, Pillow and psutil. Lock resolved dependencies with uv. Package all agents under
`uga`, retain separate commands and typed contracts.

Use deterministic pixel-level reference tests for CPU development and a separate real
Godot project. Reference simulation does not establish Godot/Windows compatibility.
External engines, decompilers and models expose explicit capability checks and require
user-authorized execution. Unsupported upstream interfaces fail with an actionable reason.

Use spawned processes for expensive jobs and a separate responsive control thread.
Do not execute untrusted analyzed binaries. Promote improvements only after comparable
benchmarks and explicit approval; retain an automatic performance rollback path.
