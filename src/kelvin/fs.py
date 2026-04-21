"""On-disk layout helpers. One source of truth for where Kelvin writes."""

from __future__ import annotations

from pathlib import Path

RUN_DIRNAME = "kelvin"


def run_root(cwd: Path) -> Path:
    """Root directory of a Kelvin run. Created under the current working dir."""
    return cwd / RUN_DIRNAME


def case_dir(cwd: Path, case: str) -> Path:
    return run_root(cwd) / case


def baseline_dir(cwd: Path, case: str) -> Path:
    return case_dir(cwd, case) / "baseline"


def perturbations_dir(cwd: Path, case: str) -> Path:
    return case_dir(cwd, case) / "perturbations"


def variant_dir(cwd: Path, case: str, variant_id: str) -> Path:
    return perturbations_dir(cwd, case) / variant_id


def ensure(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
