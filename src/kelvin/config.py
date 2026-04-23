"""Load and save `kelvin.yaml`."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_FILENAME = "kelvin.yaml"

REQUIRED_KEYS = ("run", "cases", "decision_field", "governing_types")

# Subprocess timeout default, bumped from v0.2's hardcoded 60s. LLM-backed
# pipelines routinely take >60s; 60s was effectively a v0.2 bug. Users who
# want the old behavior can set timeout_s: 60 explicitly.
_DEFAULT_TIMEOUT_S = 150


@dataclass
class NoiseFloorConfig:
    """Pillar 1 — replay baselines to establish per-pipeline stochasticity."""

    enabled: bool = False
    replications: int = 10


@dataclass
class CounterfactualSwapConfig:
    """Pillar 2 — clause-level swap holding surrounding facts constant."""

    enabled: bool = False


@dataclass
class IntraSlotConfig:
    """Pillar 3 — within-section perturbations. Off by default so v0.2 yaml
    files produce v0.2 semantics on upgrade.
    """

    enabled: bool = False
    enabled_families: list[str] = field(default_factory=list)
    governing_sentence_markers: dict = field(default_factory=dict)
    filler_stripping_whitelist: list[str] = field(default_factory=list)


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
    # Per-invocation subprocess timeout. Default 150s covers LLM-backed
    # pipelines; was hardcoded 60s in v0.2.
    timeout_s: int = _DEFAULT_TIMEOUT_S
    # v0.3 opt-in feature flags. All default off so v0.2 yaml files reproduce
    # v0.2 behaviour exactly on upgrade.
    noise_floor: NoiseFloorConfig = field(default_factory=NoiseFloorConfig)
    counterfactual_swap: CounterfactualSwapConfig = field(
        default_factory=CounterfactualSwapConfig
    )
    intra_slot: IntraSlotConfig = field(default_factory=IntraSlotConfig)

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

        timeout_s = raw.get("timeout_s", _DEFAULT_TIMEOUT_S)
        if not isinstance(timeout_s, int) or isinstance(timeout_s, bool) or timeout_s <= 0:
            raise ConfigError("`timeout_s` must be a positive integer.")

        noise_floor = _load_noise_floor(raw.get("noise_floor"))
        counterfactual_swap = _load_counterfactual_swap(raw.get("counterfactual_swap"))
        intra_slot = _load_intra_slot(raw.get("intra_slot"))

        return cls(
            run=run,
            cases=Path(cases_value),
            decision_field=decision_field,
            governing_types=list(governing_types),
            seed=seed,
            cache_dir=cache_dir,
            timeout_s=timeout_s,
            noise_floor=noise_floor,
            counterfactual_swap=counterfactual_swap,
            intra_slot=intra_slot,
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
        if self.timeout_s != _DEFAULT_TIMEOUT_S:
            data["timeout_s"] = self.timeout_s
        # Only serialize v0.3 feature blocks if they deviate from defaults,
        # keeping v0.2 yaml round-trip clean for users who haven't opted in.
        if self.noise_floor.enabled or self.noise_floor.replications != 10:
            data["noise_floor"] = {
                "enabled": self.noise_floor.enabled,
                "replications": self.noise_floor.replications,
            }
        if self.counterfactual_swap.enabled:
            data["counterfactual_swap"] = {"enabled": True}
        if (
            self.intra_slot.enabled
            or self.intra_slot.enabled_families
            or self.intra_slot.governing_sentence_markers
            or self.intra_slot.filler_stripping_whitelist
        ):
            data["intra_slot"] = {
                "enabled": self.intra_slot.enabled,
                "enabled_families": list(self.intra_slot.enabled_families),
                "governing_sentence_markers": dict(
                    self.intra_slot.governing_sentence_markers
                ),
                "filler_stripping_whitelist": list(
                    self.intra_slot.filler_stripping_whitelist
                ),
            }
        path.write_text(
            yaml.safe_dump(data, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )


def _load_noise_floor(raw) -> NoiseFloorConfig:
    if raw is None:
        return NoiseFloorConfig()
    if not isinstance(raw, dict):
        raise ConfigError("`noise_floor` must be a mapping.")
    enabled = raw.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ConfigError("`noise_floor.enabled` must be a boolean.")
    replications = raw.get("replications", 10)
    if not isinstance(replications, int) or isinstance(replications, bool) or replications < 2:
        raise ConfigError("`noise_floor.replications` must be an integer >= 2.")
    return NoiseFloorConfig(enabled=enabled, replications=replications)


def _load_counterfactual_swap(raw) -> CounterfactualSwapConfig:
    if raw is None:
        return CounterfactualSwapConfig()
    if not isinstance(raw, dict):
        raise ConfigError("`counterfactual_swap` must be a mapping.")
    enabled = raw.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ConfigError("`counterfactual_swap.enabled` must be a boolean.")
    return CounterfactualSwapConfig(enabled=enabled)


def _load_intra_slot(raw) -> IntraSlotConfig:
    if raw is None:
        return IntraSlotConfig()
    if not isinstance(raw, dict):
        raise ConfigError("`intra_slot` must be a mapping.")
    enabled = raw.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ConfigError("`intra_slot.enabled` must be a boolean.")
    families = raw.get("enabled_families", [])
    if not isinstance(families, list) or not all(isinstance(f, str) for f in families):
        raise ConfigError("`intra_slot.enabled_families` must be a list of strings.")
    markers = raw.get("governing_sentence_markers", {})
    if not isinstance(markers, dict):
        raise ConfigError("`intra_slot.governing_sentence_markers` must be a mapping.")
    whitelist = raw.get("filler_stripping_whitelist", [])
    if not isinstance(whitelist, list) or not all(isinstance(w, str) for w in whitelist):
        raise ConfigError(
            "`intra_slot.filler_stripping_whitelist` must be a list of strings."
        )
    return IntraSlotConfig(
        enabled=enabled,
        enabled_families=list(families),
        governing_sentence_markers=dict(markers),
        filler_stripping_whitelist=list(whitelist),
    )
