"""Records where a run happened. Results without hardware details are not publishable."""
from __future__ import annotations

import datetime as dt
import os
import platform
import subprocess


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return ""


def hardware() -> dict:
    info = {"os": f"{platform.system()} {platform.release()}", "arch": platform.machine()}
    if platform.system() == "Darwin":
        info["model"] = _run(["sysctl", "-n", "hw.model"])
        info["chip"] = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
        mem = _run(["sysctl", "-n", "hw.memsize"])
        info["memory_gb"] = round(int(mem) / 2**30) if mem.isdigit() else None
        info["os"] = "macOS " + _run(["sw_vers", "-productVersion"])
    elif platform.system() == "Linux":
        cpu = [l for l in _run(["cat", "/proc/cpuinfo"]).splitlines() if l.startswith("model name")]
        info["chip"] = cpu[0].split(":", 1)[1].strip() if cpu else ""
        mem = [l for l in _run(["cat", "/proc/meminfo"]).splitlines() if l.startswith("MemTotal")]
        info["memory_gb"] = round(int(mem[0].split()[1]) / 2**20) if mem else None
        gpu = _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"])
        if gpu:
            info["gpu"] = gpu
    return info


def git_sha() -> str:
    """Commit of the harness. BENCH_GIT_SHA overrides it when the code was copied without .git."""
    return os.environ.get("BENCH_GIT_SHA") or _run(["git", "rev-parse", "--short", "HEAD"])


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def label() -> str:
    """Optional human label for the machine, e.g. 'Mac mini M4 Pro 64GB'."""
    return os.environ.get("BENCH_MACHINE", "")
