from pathlib import Path

from pydantic import DirectoryPath, FilePath, ValidationError, field_validator

from uga.core.contracts import Contract
from uga.core.errors import CapabilityUnavailable


class AnalysisTools(Contract):
    java: FilePath | None = None
    jadx_installation: DirectoryPath | None = None
    ghidra: FilePath | None = None

    @field_validator("java", "jadx_installation", "ghidra")
    @classmethod
    def absolute_path(cls, value):
        if value is not None and not value.is_absolute():
            raise ValueError("tool paths must be absolute")
        return value


def load_analysis_tools(root: Path) -> AnalysisTools:
    path = root / "analysis-tools.json"
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 16384:
        raise CapabilityUnavailable(
            "Configure owned analyzer paths in the state directory analysis-tools.json"
        )
    try:
        return AnalysisTools.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise CapabilityUnavailable(
            "Invalid analysis-tools.json; use absolute installed tool paths"
        ) from exc
