"""Optional local REAPER command-line integration."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def find_reaper(executable: str | None = None) -> str:
    if executable:
        path = Path(executable)
        if path.exists():
            return str(path)
        found = shutil.which(executable)
        if found:
            return found
        raise FileNotFoundError(f"REAPER executable not found: {executable}")
    for candidate in ("reaper", "reaper.exe"):
        found = shutil.which(candidate)
        if found:
            return found
    raise FileNotFoundError("REAPER was not found on PATH. Set the executable path in the app or use REAPER locally.")


def render_project(project_path: str | Path, executable: str | None = None,
                   timeout_seconds: int = 1800) -> subprocess.CompletedProcess:
    project = Path(project_path).resolve()
    if not project.exists() or project.suffix.lower() != ".rpp":
        raise ValueError("A valid .RPP project file is required")
    exe = find_reaper(executable)
    # REAPER uses the project's saved render settings; this command does not
    # invent a codec, range, destination, sample rate or track/stem configuration.
    return subprocess.run([exe, "-renderproject", str(project)], capture_output=True,
                          text=True, timeout=timeout_seconds, check=False)
