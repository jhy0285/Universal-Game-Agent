import importlib.util
import platform
import shutil

from uga import __version__


def capabilities() -> dict:
    return {
        "version": __version__,
        "python": platform.python_version(),
        "platform": platform.system(),
        "cpu_fallback": True,
        "desktop_capture": importlib.util.find_spec("mss") is not None,
        "windows_input": platform.system() == "Windows",
        "godot": shutil.which("godot") or shutil.which("godot4"),
        "jadx": shutil.which("jadx"),
        "ghidra": shutil.which("analyzeHeadless"),
        "laya": {"available": False, "reason": "upstream model and inference API not verified"},
        "rea": {"available": False, "reason": "external integration not configured"},
        "unity": {"available": False, "reason": "Unity Editor/license required"},
    }
