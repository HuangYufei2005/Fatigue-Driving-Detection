import os
import subprocess
import sys
from pathlib import Path


def get_project_venv_python() -> Path | None:
    root = Path(__file__).resolve().parents[1]
    candidates = [
        root / ".venv" / "Scripts" / "python.exe",
        root / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def maybe_reexec_into_project_venv() -> None:
    if os.environ.get("FATIGUE_TEST_VENV_ACTIVE") == "1":
        return

    venv_python = get_project_venv_python()
    if not venv_python:
        return

    try:
        current = Path(sys.executable).resolve()
        target = venv_python.resolve()
    except Exception:
        current = Path(sys.executable)
        target = venv_python

    if current == target:
        return

    env = os.environ.copy()
    env["FATIGUE_TEST_VENV_ACTIVE"] = "1"
    result = subprocess.run([str(venv_python), sys.argv[0], *sys.argv[1:]], env=env)
    raise SystemExit(result.returncode)
