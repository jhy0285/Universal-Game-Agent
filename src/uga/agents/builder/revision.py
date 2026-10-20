"""Hash-checked candidate edits. Existing projects are never changed in place."""

import hashlib
import os
import shutil
import tempfile
from pathlib import Path, PurePosixPath

from pydantic import Field, field_validator

from uga.agents.builder.pipeline import validate_project
from uga.core.contracts import Contract
from uga.core.errors import AuthorizationRequired, UGAError
from uga.memory.store import atomic_json

TEXT_SUFFIXES = {".gd", ".tscn", ".tres", ".godot", ".cfg", ".json", ".txt", ".md", ".uid"}
RESOURCE_SUFFIXES = TEXT_SUFFIXES | {".png", ".svg", ".wav", ".ogg"}
SKIP = {".git", ".godot", ".uga", ".venv", "node_modules", "build", "__pycache__"}


class TextEdit(Contract):
    path: str = Field(min_length=1, max_length=256)
    expected_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    content: str = Field(max_length=1_000_000)

    @field_validator("path")
    @classmethod
    def relative_text_file(cls, value):
        path = PurePosixPath(value)
        if (
            path.is_absolute()
            or ".." in path.parts
            or not path.parts
            or any(c in value for c in ("\\", ":", "\0", "\n", "\r"))
            or str(path) != value
            or path.suffix not in TEXT_SUFFIXES
            or any(part.startswith(".") for part in path.parts)
        ):
            raise ValueError("edit path must be a relative Godot text resource")
        return value


class PatchPlan(Contract):
    summary: str = Field(min_length=1, max_length=2000)
    edits: list[TextEdit] = Field(min_length=1, max_length=16)


def _clone(source, destination):
    if source.is_symlink() or not source.is_dir() or not (source / "project.godot").is_file():
        raise ValueError("regular Godot project directory required")
    destination.mkdir()
    total = count = 0
    for current, dirs, files in os.walk(source, followlinks=False):
        dirs[:] = [name for name in sorted(dirs) if name not in SKIP and not name.startswith(".")]
        if any((Path(current) / name).is_symlink() for name in dirs):
            raise ValueError("project symlink directories are not admitted")
        for name in sorted(files):
            path = Path(current) / name
            if name.startswith("."):
                continue
            if path.is_symlink() or not path.is_file():
                raise ValueError("project symlinks and special files are not admitted")
            if path.suffix not in RESOURCE_SUFFIXES:
                raise ValueError("unsupported project resource: " + name)
            if path.stat().st_size > 8_000_000:
                raise ValueError("project resource exceeds 8 MB")
            with path.open("rb") as stream:
                data = stream.read(8_000_001)
            total += len(data)
            count += 1
            if len(data) > 8_000_000 or total > 32_000_000 or count > 256:
                raise ValueError("project revision exceeds copy budget")
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)


def apply_plan(project: Path, plan: PatchPlan):
    paths = set()
    replacements = []
    for edit in plan.edits:
        if edit.path in paths:
            raise ValueError("duplicate edit path")
        paths.add(edit.path)
        target = project / edit.path
        if (
            target.is_symlink()
            or not target.is_file()
            or not target.resolve().is_relative_to(project.resolve())
        ):
            raise ValueError("edit must match an existing regular project file")
        if hashlib.sha256(target.read_bytes()).hexdigest() != edit.expected_sha256:
            raise ValueError("source hash changed: " + edit.path)
        content = edit.content.encode("utf-8")
        if len(content) > 1_000_000:
            raise ValueError("UTF-8 edit exceeds 1 MB")
        replacements.append((target, content, edit))
    audit = []
    for target, content, edit in replacements:
        temporary = target.with_name(target.name + ".uga-edit-tmp")
        temporary.write_bytes(content)
        temporary.replace(target)
        audit.append(
            {
                "path": edit.path,
                "before_sha256": edit.expected_sha256,
                "after_sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return {"summary": plan.summary, "edits": audit}


def _candidate(source: Path, output: Path, plan: PatchPlan | None):
    if source.is_symlink():
        raise ValueError("symlink project root is not admitted")
    source, output = source.resolve(), output.resolve()
    if output.exists():
        raise FileExistsError("Revision output must be new")
    if output.is_relative_to(source):
        raise ValueError("revision output must be outside its source project")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".uga-revision-", dir=output.parent))
    try:
        _clone(source, temporary / "project")
        audit = apply_plan(temporary / "project", plan) if plan else None
        temporary.rename(output)
        return audit
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def revise_project(source, output, plan, *, authorized=False, validate=False, approved=False):
    if not authorized or (validate and not approved):
        raise AuthorizationRequired(
            "Revision needs project authorization and engine execution approval"
        )
    audit = _candidate(source, output, plan)
    report = {"status": "candidate", "project": str((output / "project").resolve()), "patch": audit}
    atomic_json(output / "revision.json", report)
    if validate:
        try:
            report["engine"] = validate_project(
                output / "project", output / "validation", approved=True
            )
            report["status"] = "verified"
        except (UGAError, OSError, ValueError) as exc:
            report.update(status="failed", error=str(exc))
            atomic_json(output / "revision.json", report)
            raise
        atomic_json(output / "revision.json", report)
    return report


def known_template_repair(project, error):
    """One evidenced Godot Array typing repair; no speculative code synthesis."""
    path = project / "main.gd"
    if not path.is_file() or "Array[Rect2]" not in error:
        return None
    source = path.read_text(encoding="utf-8")
    before = '    walls = [Rect2(72, 28, 9, 53)] if config.get("obstacles", true) else []'
    after = '    walls.clear()\n    if config.get("obstacles", true):\n        walls.append(Rect2(72, 28, 9, 53))'
    if source.count(before) != 1:
        return None
    return PatchPlan(
        summary="Repair the confirmed UGA obstacle Array[Rect2] assignment",
        edits=[
            TextEdit(
                path="main.gd",
                expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                content=source.replace(before, after),
            )
        ],
    )


def repair_project(source, output, *, authorized=False, approved=False):
    if not authorized or not approved:
        raise AuthorizationRequired(
            "Repair needs project authorization and Godot execution approval"
        )
    _candidate(source, output, None)
    report = {"status": "testing", "project": str((output / "project").resolve()), "attempts": []}
    for attempt in range(2):
        try:
            report["engine"] = validate_project(
                output / "project", output / f"validation-{attempt}", approved=True
            )
            report["status"] = "verified"
            atomic_json(output / "revision.json", report)
            return report
        except (UGAError, OSError, ValueError) as exc:
            error = str(exc)
            plan = known_template_repair(output / "project", error) if attempt == 0 else None
            entry = {"attempt": attempt, "error": error}
            if plan:
                entry["patch"] = apply_plan(output / "project", plan)
            report["attempts"].append(entry)
            report["status"] = "retrying" if plan else "failed"
            atomic_json(output / "revision.json", report)
            if plan is None:
                raise
    raise UGAError("repair attempt limit exceeded")
