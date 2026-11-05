"""Installer-only scheduling and read-only health samples; no firmware changes."""
import os
from pathlib import Path


def gentler():
    """The worker and its children use at most two available logical CPUs."""
    available = sorted(os.sched_getaffinity(0))
    if not available:
        raise OSError('No CPUs are available to the installer')
    selected = available[:2]
    os.sched_setaffinity(0, selected)
    os.nice(10)
    os.environ['RAYON_NUM_THREADS'] = str(len(selected))
    os.environ['OMP_NUM_THREADS'] = str(len(selected))
    return len(selected)


def sample(thermal=Path('/sys/class/thermal'), memory=Path('/proc/meminfo')):
    temperatures = []
    for path in thermal.glob('thermal_zone*/temp'):
        try:
            value = int(path.read_text().strip()) / 1000
            if 0 < value < 150:
                temperatures.append(value)
        except (OSError, ValueError):
            pass
    available = None
    try:
        for line in memory.read_text().splitlines():
            if line.startswith('MemAvailable:'):
                available = max(0, int(line.split()[1])) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return dict(temperature=max(temperatures) if temperatures else None, available=available)
