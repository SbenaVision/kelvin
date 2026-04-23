"""Load and save `kelvin.yaml`."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from kelvin.messages import (
    CONFIG_CACHE_DIR_INVALID,
    CONFIG_CASES_INVALID,
    CONFIG_COUNTERFACTUAL_SWAP_ENABLED_INVALID,
    CONFIG_COUNTERFACTUAL_SWAP_NOT_MAPPING,
    CONFIG_DECISION_FIELD_INVALID,
    CONFIG_FILE_NOT_FOUND,
    CONFIG_GOVERNING_TYPES_INVALID,
    CONFIG_INTRA_SLOT_ENABLED_INVALID,
    CONFIG_INTRA_SLOT_FAMILIES_INVALID,
    CONFIG_INTRA_SLOT_MARKERS_INVALID,
    CONFIG_INTRA_SLOT_NOT_MAPPING,
    CONFIG_INTRA_SLOT_WHITELIST_INVALID,
    CONFIG_MISSING_KEYS,
    CONFIG_NOISE_FLOOR_ENABLED_INVALID,
    CONFIG_NOISE_FLOOR_NOT_MAPPING,
    CONFIG_NOISE_FLOOR_REPLICATIONS_INVALID,
    CONFIG_NOT_MAPPING,
    CONFIG_RETRY_POLICY_BACKOFF_FACTOR_INVALID,
    CONFIG_RETRY_POLICY_INITIAL_DELAY_INVALID,
    CONFIG_RETRY_POLICY_JITTER_MAX_INVALID,
    CONFIG_RETRY_POLICY_MAX_ATTEMPTS_INVALID,
    CONFIG_RETRY_POLICY_NOT_MAPPING,
    CONFIG_RETRY_POLICY_RETRY_ON_TIMEOUT_INVALID,
    CONFIG_RETRY_POLICY_TRANSIENT_CODES_INVALID,
    CONFIG_RUN_INVALID,
    CONFIG_RUN_MISSING_PLACEHOLDERS,
    CONFIG_SEED_INVALID,
    CONFIG_TIMEOUT_INVALID,
    CONFIG_YAML_PARSE_ERROR,
    FormattedMessage,
    catalog,
)
from kelvin.retry import RetryPolicy

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
    """Raised when kelvin.yaml is missing, malformed, or has bad values.

    Accepts either a `FormattedMessage` (preferred — carries the full
    what/why/how-to-fix triple for terminal + structured rendering) or a
    plain string (backward-compatible fallback). When constructed with a
    `FormattedMessage`, the rendered text goes into `str(error)` and the
    original message is accessible via `error.formatted_message`.
    """

    def __init__(self, message_or_text: Any, /) -> None:
        if isinstance(message_or_text, FormattedMessage):
            self.formatted_message: FormattedMessage | None = message_or_text
            super().__init__(message_or_text.as_text())
        else:
            self.formatted_message = None
            super().__init__(str(message_or_text))


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
    # Optional retry policy for the core runner. When omitted or defaulted,
    # no retry fires — v0.2-byte-compat.
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)

    @classmethod
    def load(cls, path: Path) -> KelvinConfig:
        if not path.exists():
            raise ConfigError(catalog(CONFIG_FILE_NOT_FOUND, path=path))
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ConfigError(
                catalog(CONFIG_YAML_PARSE_ERROR, path=path, detail=exc)
            ) from exc
        if not isinstance(raw, dict):
            raise ConfigError(catalog(CONFIG_NOT_MAPPING, path=path))

        missing = [k for k in REQUIRED_KEYS if k not in raw]
        if missing:
            raise ConfigError(
                catalog(
                    CONFIG_MISSING_KEYS, path=path, missing=", ".join(missing)
                )
            )

        run = raw["run"]
        if not isinstance(run, str) or not run.strip():
            raise ConfigError(catalog(CONFIG_RUN_INVALID))
        if "{input}" not in run or "{output}" not in run:
            raise ConfigError(catalog(CONFIG_RUN_MISSING_PLACEHOLDERS))

        cases_value = raw["cases"]
        if not isinstance(cases_value, str) or not cases_value.strip():
            raise ConfigError(catalog(CONFIG_CASES_INVALID))

        decision_field = raw["decision_field"]
        if not isinstance(decision_field, str) or not decision_field.strip():
            raise ConfigError(catalog(CONFIG_DECISION_FIELD_INVALID))

        governing_types = raw["governing_types"]
        if not isinstance(governing_types, list) or not all(
            isinstance(t, str) for t in governing_types
        ):
            raise ConfigError(catalog(CONFIG_GOVERNING_TYPES_INVALID))

        seed = raw.get("seed", 0)
        if not isinstance(seed, int):
            raise ConfigError(catalog(CONFIG_SEED_INVALID))

        cache_raw = raw.get("cache_dir", None)
        cache_dir: Path | None
        if cache_raw is None:
            cache_dir = None
        elif isinstance(cache_raw, str) and cache_raw.strip():
            cache_dir = Path(cache_raw)
        else:
            raise ConfigError(catalog(CONFIG_CACHE_DIR_INVALID))

        timeout_s = raw.get("timeout_s", _DEFAULT_TIMEOUT_S)
        if not isinstance(timeout_s, int) or isinstance(timeout_s, bool) or timeout_s <= 0:
            raise ConfigError(catalog(CONFIG_TIMEOUT_INVALID, value=timeout_s))

        noise_floor = _load_noise_floor(raw.get("noise_floor"))
        counterfactual_swap = _load_counterfactual_swap(raw.get("counterfactual_swap"))
        intra_slot = _load_intra_slot(raw.get("intra_slot"))
        retry_policy = _load_retry_policy(raw.get("retry_policy"))

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
            retry_policy=retry_policy,
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
        _default_retry = RetryPolicy()
        if (
            self.retry_policy.max_attempts != _default_retry.max_attempts
            or self.retry_policy.initial_delay_s != _default_retry.initial_delay_s
            or self.retry_policy.backoff_factor != _default_retry.backoff_factor
            or self.retry_policy.jitter_max_s != _default_retry.jitter_max_s
            or self.retry_policy.transient_exit_codes
            or self.retry_policy.retry_on_timeout
        ):
            data["retry_policy"] = {
                "max_attempts": self.retry_policy.max_attempts,
                "initial_delay_s": self.retry_policy.initial_delay_s,
                "backoff_factor": self.retry_policy.backoff_factor,
                "jitter_max_s": self.retry_policy.jitter_max_s,
                "transient_exit_codes": sorted(self.retry_policy.transient_exit_codes),
                "retry_on_timeout": self.retry_policy.retry_on_timeout,
            }
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
        raise ConfigError(catalog(CONFIG_NOISE_FLOOR_NOT_MAPPING))
    enabled = raw.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ConfigError(catalog(CONFIG_NOISE_FLOOR_ENABLED_INVALID))
    replications = raw.get("replications", 10)
    if not isinstance(replications, int) or isinstance(replications, bool) or replications < 2:
        raise ConfigError(catalog(CONFIG_NOISE_FLOOR_REPLICATIONS_INVALID))
    return NoiseFloorConfig(enabled=enabled, replications=replications)


def _load_counterfactual_swap(raw) -> CounterfactualSwapConfig:
    if raw is None:
        return CounterfactualSwapConfig()
    if not isinstance(raw, dict):
        raise ConfigError(catalog(CONFIG_COUNTERFACTUAL_SWAP_NOT_MAPPING))
    enabled = raw.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ConfigError(catalog(CONFIG_COUNTERFACTUAL_SWAP_ENABLED_INVALID))
    return CounterfactualSwapConfig(enabled=enabled)


def _load_retry_policy(raw) -> RetryPolicy:
    if raw is None:
        return RetryPolicy()
    if not isinstance(raw, dict):
        raise ConfigError(catalog(CONFIG_RETRY_POLICY_NOT_MAPPING))

    def _float(raw_value, default):
        # YAML loads 1 as int, 1.0 as float — accept both, reject bool.
        if isinstance(raw_value, bool):
            return None
        if isinstance(raw_value, (int, float)):
            return float(raw_value)
        return None

    defaults = RetryPolicy()

    max_attempts = raw.get("max_attempts", defaults.max_attempts)
    if not isinstance(max_attempts, int) or isinstance(max_attempts, bool) or max_attempts < 1:
        raise ConfigError(catalog(CONFIG_RETRY_POLICY_MAX_ATTEMPTS_INVALID))

    initial_delay = _float(
        raw.get("initial_delay_s", defaults.initial_delay_s), defaults.initial_delay_s
    )
    if initial_delay is None or initial_delay < 0:
        raise ConfigError(catalog(CONFIG_RETRY_POLICY_INITIAL_DELAY_INVALID))

    backoff = _float(
        raw.get("backoff_factor", defaults.backoff_factor), defaults.backoff_factor
    )
    if backoff is None or backoff < 1.0:
        raise ConfigError(catalog(CONFIG_RETRY_POLICY_BACKOFF_FACTOR_INVALID))

    jitter = _float(
        raw.get("jitter_max_s", defaults.jitter_max_s), defaults.jitter_max_s
    )
    if jitter is None or jitter < 0:
        raise ConfigError(catalog(CONFIG_RETRY_POLICY_JITTER_MAX_INVALID))

    codes_raw = raw.get("transient_exit_codes", [])
    if not isinstance(codes_raw, list) or not all(
        isinstance(c, int) and not isinstance(c, bool) for c in codes_raw
    ):
        raise ConfigError(catalog(CONFIG_RETRY_POLICY_TRANSIENT_CODES_INVALID))

    retry_on_timeout = raw.get("retry_on_timeout", defaults.retry_on_timeout)
    if not isinstance(retry_on_timeout, bool):
        raise ConfigError(catalog(CONFIG_RETRY_POLICY_RETRY_ON_TIMEOUT_INVALID))

    return RetryPolicy(
        max_attempts=max_attempts,
        initial_delay_s=initial_delay,
        backoff_factor=backoff,
        jitter_max_s=jitter,
        transient_exit_codes=frozenset(codes_raw),
        retry_on_timeout=retry_on_timeout,
    )


def _load_intra_slot(raw) -> IntraSlotConfig:
    if raw is None:
        return IntraSlotConfig()
    if not isinstance(raw, dict):
        raise ConfigError(catalog(CONFIG_INTRA_SLOT_NOT_MAPPING))
    enabled = raw.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ConfigError(catalog(CONFIG_INTRA_SLOT_ENABLED_INVALID))
    families = raw.get("enabled_families", [])
    if not isinstance(families, list) or not all(isinstance(f, str) for f in families):
        raise ConfigError(catalog(CONFIG_INTRA_SLOT_FAMILIES_INVALID))
    markers = raw.get("governing_sentence_markers", {})
    if not isinstance(markers, dict):
        raise ConfigError(catalog(CONFIG_INTRA_SLOT_MARKERS_INVALID))
    whitelist = raw.get("filler_stripping_whitelist", [])
    if not isinstance(whitelist, list) or not all(isinstance(w, str) for w in whitelist):
        raise ConfigError(catalog(CONFIG_INTRA_SLOT_WHITELIST_INVALID))
    return IntraSlotConfig(
        enabled=enabled,
        enabled_families=list(families),
        governing_sentence_markers=dict(markers),
        filler_stripping_whitelist=list(whitelist),
    )
