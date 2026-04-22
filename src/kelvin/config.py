"""Load and save `kelvin.yaml`."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_FILENAME = "kelvin.yaml"

REQUIRED_KEYS = ("run", "cases", "decision_field", "governing_types")


class ConfigError(ValueError):
    """Raised when kelvin.yaml is missing, malformed, or has bad values."""


@dataclass
class KelvinConfig:
    run: str
    cases: Path
    decision_field: str
    governing_types: list[str] = field(default_factory=list)
    seed: int = 0
    # Opt-in on-disk invocation cache. Key =
    # sha256(run + rendered_markdown + decision_field); value =
    # serialized InvocationResult. Relative paths resolve against cwd.
    # None (default): disabled.
    cache_dir: Path | None = None

    @classmethod
    def load(cls, path: Path) -> KelvinConfig:
        if not path.exists():
            raise ConfigError(f"{path} not found. Run `kelvin init` first.")
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ConfigError(f"{path} is not valid YAML: {exc}") from exc
        if not isinstance(raw, dict):
            raise ConfigError(f"{path} must contain a YAML mapping at the top level.")

        missing = [k for k in REQUIRED_KEYS if k not in raw]
        if missing:
            raise ConfigError(
                f"{path} is missing required keys: {', '.join(missing)}."
            )

        run = raw["run"]
        if not isinstance(run, str) or not run.strip():
            raise ConfigError("`run` must be a non-empty string shell-command template.")
        if "{input}" not in run or "{output}" not in run:
            raise ConfigError(
                "`run` must contain both `{input}` and `{output}` placeholders."
            )

        cases_value = raw["cases"]
        if not isinstance(cases_value, str) or not cases_value.strip():
            raise ConfigError("`cases` must be a non-empty path string.")

        decision_field = raw["decision_field"]
        if not isinstance(decision_field, str) or not decision_field.strip():
            raise ConfigError("`decision_field` must be a non-empty string.")

        governing_types = raw["governing_types"]
        if not isinstance(governing_types, list) or not all(
            isinstance(t, str) for t in governing_types
        ):
            raise ConfigError("`governing_types` must be a list of strings.")

        seed = raw.get("seed", 0)
        if not isinstance(seed, int):
            raise ConfigError("`seed` must be an integer.")

        cache_raw = raw.get("cache_dir", None)
        cache_dir: Path | None
        if cache_raw is None:
            cache_dir = None
        elif isinstance(cache_raw, str) and cache_raw.strip():
            cache_dir = Path(cache_raw)
        else:
            raise ConfigError(
                "`cache_dir` must be a non-empty string path, or omitted to disable."
            )

        return cls(
            run=run,
            cases=Path(cases_value),
            decision_field=decision_field,
            governing_types=list(governing_types),
            seed=seed,
            cache_dir=cache_dir,
        )

    def save(self, path: Path) -> None:
        data: dict = {
            "run": self.run,
            "cases": str(self.cases),
            "decision_field": self.decision_field,
            "governing_types": list(self.governing_types),
            "seed": self.seed,
        }
        if self.cache_dir is not None:
            data["cache_dir"] = str(self.cache_dir)
        path.write_text(
            yaml.safe_dump(data, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )
