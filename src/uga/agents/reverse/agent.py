import hashlib
import io
import os
import re
import zipfile
from pathlib import Path, PurePosixPath

from uga.core.contracts import Finding, GameSpec
from uga.core.errors import AuthorizationRequired
from uga.memory.store import atomic_json

MAX_FILE = 32 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
MAX_FILES = 2048
SKIP = {".git", ".godot", ".uga", ".venv", "node_modules", "__pycache__"}
TEXT = {".gd", ".cs", ".java", ".py", ".json", ".tscn", ".xml", ".cfg", ".txt"}


def _read(path: Path) -> bytes:
    if path.is_symlink():
        raise ValueError("symlink samples are not admitted")
    if not path.is_file():
        raise ValueError("sample must be a regular file")
    if path.stat().st_size > MAX_FILE:
        raise ValueError("sample exceeds 32 MiB limit")
    with path.open("rb") as stream:
        data = stream.read(MAX_FILE + 1)
    if len(data) > MAX_FILE:
        raise ValueError("sample grew beyond limit")
    return data


def analyze(path: Path, output: Path, *, authorized: bool = False) -> GameSpec:
    if not authorized:
        raise AuthorizationRequired(
            "Confirm that you own or have permission to analyze this target"
        )
    if path.is_symlink():
        raise ValueError("symlink target is not admitted")
    path = path.resolve()
    output = output.resolve()
    sources = []
    if path.is_dir():
        for current, dirs, names in os.walk(
            path, followlinks=False, onerror=lambda e: (_ for _ in ()).throw(e)
        ):
            dirs[:] = [d for d in sorted(dirs) if d not in SKIP]
            for directory in dirs:
                if (Path(current) / directory).is_symlink():
                    raise ValueError("symlink directory in sample")
            for name in sorted(names):
                candidate = Path(current) / name
                if candidate.resolve().is_relative_to(output):
                    continue
                sources.append(candidate)
                if len(sources) > MAX_FILES:
                    raise ValueError("too many sample files")
    else:
        sources = [path]
    findings = []
    declared_specs = []
    structure = []
    total = 0
    for source in sources:
        data = _read(source)
        total += len(data)
        if total > MAX_TOTAL:
            raise ValueError("sample total exceeds 64 MiB limit")
        relative = str(source.relative_to(path)) if path.is_dir() else source.name
        digest = hashlib.sha256(data).hexdigest()
        origin = f"sha256:{digest}:{relative}"
        findings.append(
            Finding(
                subject=relative,
                statement=f"File size {len(data)} bytes; SHA-256 {digest}",
                source=origin,
                confidence=1,
            )
        )
        if source.suffix.lower() in (".apk", ".zip", ".jar", ".aab"):
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                members = archive.infolist()
                if len(members) > MAX_FILES:
                    raise ValueError("archive member limit exceeded")
                size = 0
                for member in members:
                    normalized = PurePosixPath(member.filename.replace("\\", "/"))
                    if (
                        normalized.is_absolute()
                        or ".." in normalized.parts
                        or ":" in member.filename
                        or len(member.filename) > 512
                    ):
                        raise ValueError("unsafe archive member name")
                    size += member.file_size
                    if (
                        size > MAX_TOTAL
                        or member.file_size > MAX_FILE
                        or member.file_size / max(1, member.compress_size) > 200
                    ):
                        raise ValueError("archive expansion limit exceeded")
                    if member.flag_bits & 1:
                        raise ValueError("encrypted archives are not supported")
                names = [m.filename for m in members]
                dex = [n for n in names if n.endswith(".dex")]
                resources = [n for n in names if n.startswith(("res/", "assets/"))]
                structure.append(
                    {
                        "source": relative,
                        "kind": "archive",
                        "members": names,
                        "dex_files": dex,
                        "resources": resources,
                        "decompiled": False,
                    }
                )
                findings.append(
                    Finding(
                        subject=relative,
                        statement=f"Archive contains {len(dex)} DEX and {len(resources)} resource entries; names only, no decompilation",
                        source=origin,
                        confidence=1,
                    )
                )
        elif source.suffix.lower() in TEXT:
            text = data.decode("utf-8", "replace")
            if source.name == "game_spec.json":
                try:
                    declared_specs.append(GameSpec.model_validate_json(text))
                    findings.append(
                        Finding(
                            subject="declared GameSpec",
                            statement="Source configuration declares a versioned GameSpec; runtime behavior not verified",
                            source=origin,
                            confidence=1,
                        )
                    )
                except ValueError:
                    findings.append(
                        Finding(
                            subject="invalid GameSpec",
                            statement="Source configuration is not a valid GameSpec 1.0",
                            source=origin,
                            confidence=1,
                        )
                    )
            classes = []
            functions = []
            calls = []
            for number, line in enumerate(text.splitlines(), 1):
                c = re.search(r"^\s*(?:class_name|class)\s+(\w+)", line)
                f = re.search(
                    r"^\s*(?:func|def|(?:public|private|protected)\s+\w+)\s+(\w+)\s*\(", line
                )
                if c:
                    classes.append({"name": c.group(1), "line": number})
                if f:
                    functions.append({"name": f.group(1), "line": number})
                calls.extend(
                    {"name": n, "line": number} for n in re.findall(r"\b(\w+)\s*\(", line)[:30]
                )
            structure.append(
                {
                    "source": relative,
                    "kind": "source",
                    "classes": classes,
                    "functions": functions,
                    "syntactic_call_sites": calls,
                    "semantic_resolution": False,
                }
            )
            for f in functions:
                findings.append(
                    Finding(
                        subject=f["name"],
                        statement="Source function declaration",
                        source=f"{origin}:{f['line']}",
                        confidence=1,
                    )
                )
        else:
            kind = (
                "ELF"
                if data.startswith(b"\x7fELF")
                else "PE/DOS"
                if data.startswith(b"MZ")
                else "unknown"
            )
            structure.append({"source": relative, "kind": kind, "disassembled": False})
    spec = GameSpec(
        name=(path.stem or "sample")[:100],
        findings=findings,
        requirements=[
            "Game mechanics remain unknown without sufficient source/decompiler evidence"
        ],
    )
    if len(declared_specs) == 1:
        declared = declared_specs[0]
        spec = declared.model_copy(deep=True)
        spec.findings = findings
        spec.requirements.append(
            "Mechanics copied from a source declaration, not established by runtime analysis"
        )
    elif len(declared_specs) > 1:
        spec.requirements.append("Multiple GameSpec declarations require human resolution")
    output.mkdir(parents=True, exist_ok=True)
    atomic_json(output / "game-spec.json", spec.model_dump(mode="json"))
    atomic_json(
        output / "structure.json",
        {"sources": structure, "executed_samples": False, "total_bytes": total},
    )
    return spec
