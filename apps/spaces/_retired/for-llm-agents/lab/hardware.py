"""Hardware disclosure (same rule as the Speed Arena harness, R4).

Every measured number on this Space is printed next to the machine that
produced it: host, CPU, cores, RAM, OS, Python and NumPy versions.
"""

from __future__ import annotations

import os
import platform

LAB_VERSION = "1.0.0"


def _cpu_model() -> str:
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    if platform.system() == "Darwin":
        import subprocess

        try:
            out = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if out.stdout.strip():
                return out.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return platform.processor() or platform.machine()


def _ram_gb() -> float:
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("MemTotal"):
                    return int(line.split()[1]) / 1e6
    except OSError:
        pass
    if platform.system() == "Darwin":
        import subprocess

        try:
            out = subprocess.run(
                ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5
            )
            return int(out.stdout.strip()) / 1e9
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    return 0.0


def hardware_footer() -> str:
    """The machine behind every number on this Space."""
    import numpy

    space = os.environ.get("SPACE_ID") or os.environ.get("HF_SPACE_ID") or ""
    host = f"HF Space {space} (cpu-basic)" if space else "local run"
    return (
        f"{host} · {_cpu_model()} · {os.cpu_count()} vCPU · {_ram_gb():.0f} GB RAM · "
        f"{platform.system()} {platform.release()} {platform.machine()} · "
        f"Python {platform.python_version()} · NumPy {numpy.__version__} · "
        f"agents-lab v{LAB_VERSION}"
    )
