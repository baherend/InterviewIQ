from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any


def run_json_component(command: list[str], cwd: Path, env: dict[str, str],
                       timeout: int) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    started = time.monotonic()
    execution: dict[str, Any] = {"command": command, "cwd": str(cwd), "timeout_seconds": timeout}
    try:
        cp = subprocess.run(command, cwd=str(cwd), env=env, capture_output=True,
                            text=True, encoding="utf-8", errors="replace",
                            timeout=timeout, check=False, shell=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        execution.update(status="failed", duration_seconds=round(time.monotonic() - started, 3),
                         error={"type": type(exc).__name__, "message": str(exc)})
        return None, execution
    execution.update(return_code=cp.returncode, duration_seconds=round(time.monotonic() - started, 3),
                     stderr=cp.stderr, status="completed" if cp.returncode == 0 else "failed")
    try:
        parsed = json.loads(cp.stdout)
        if not isinstance(parsed, dict):
            raise ValueError("JSON output is not an object")
    except (json.JSONDecodeError, ValueError) as exc:
        execution["status"] = "failed"
        execution["error"] = {"type": "InvalidComponentJSON", "message": str(exc),
                              "stdout": cp.stdout}
        return None, execution
    if cp.returncode != 0:
        execution["error"] = parsed.get("error", {"type": "ComponentFailure", "message": "Non-zero exit"})
        return parsed, execution
    return parsed, execution
