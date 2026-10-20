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
        "laya": {
            "available": importlib.util.find_spec("laya") is not None,
            "upstream": "https://github.com/NandhaKishorM/laya",
            "reason": "Router API verified; local weights/inference not validated",
        },
        "rea": {"available": False, "reason": "external integration not configured"},
        "unity": {"available": False, "reason": "Unity Editor/license required"},
    }
