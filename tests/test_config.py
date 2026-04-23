from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from kelvin.config import (
    CONFIG_FILENAME,
    ConfigError,
    CounterfactualSwapConfig,
    IntraSlotConfig,
    KelvinConfig,
    NoiseFloorConfig,
)

VALID_YAML = """\
run: python -m pipe --input {input} --output {output}
cases: ./ventures
decision_field: recommendation
governing_types: [gate_rule]
seed: 42
"""


def write_yaml(tmp: Path, content: str) -> Path:
    p = tmp / CONFIG_FILENAME
    p.write_text(content, encoding="utf-8")
    return p


class TestLoad:
    def test_parses_a_valid_config(self, tmp_path: Path) -> None:
        cfg = KelvinConfig.load(write_yaml(tmp_path, VALID_YAML))
        assert cfg.run.startswith("python -m pipe")
        assert cfg.cases == Path("./ventures")
        assert cfg.decision_field == "recommendation"
        assert cfg.governing_types == ["gate_rule"]
        assert cfg.seed == 42

    def test_seed_defaults_to_zero_when_omitted(self, tmp_path: Path) -> None:
        yaml_text = (
            "run: cmd --input {input} --output {output}\n"
            "cases: ./c\n"
            "decision_field: d\n"
            "governing_types: []\n"
        )
        cfg = KelvinConfig.load(write_yaml(tmp_path, yaml_text))
        assert cfg.seed == 0

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="not found"):
            KelvinConfig.load(tmp_path / "missing.yaml")

    def test_missing_required_key_raises(self, tmp_path: Path) -> None:
        bad = (
            "run: cmd --input {input} --output {output}\n"
            "cases: ./c\n"
            "governing_types: []\n"
        )
        with pytest.raises(ConfigError, match="decision_field"):
            KelvinConfig.load(write_yaml(tmp_path, bad))

    def test_non_mapping_root_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="mapping"):
            KelvinConfig.load(write_yaml(tmp_path, "- just a list\n"))

    def test_invalid_yaml_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="not valid YAML"):
            KelvinConfig.load(write_yaml(tmp_path, "run: [unclosed\n"))

    def test_run_without_input_placeholder_raises(self, tmp_path: Path) -> None:
        bad = (
            "run: cmd --output {output}\n"
            "cases: ./c\n"
            "decision_field: d\n"
            "governing_types: []\n"
        )
        with pytest.raises(ConfigError, match=r"\{input\}"):
            KelvinConfig.load(write_yaml(tmp_path, bad))

    def test_run_without_output_placeholder_raises(self, tmp_path: Path) -> None:
        bad = (
            "run: cmd --input {input}\n"
            "cases: ./c\n"
            "decision_field: d\n"
            "governing_types: []\n"
        )
        with pytest.raises(ConfigError, match=r"\{output\}"):
            KelvinConfig.load(write_yaml(tmp_path, bad))

    def test_empty_run_raises(self, tmp_path: Path) -> None:
        bad = (
            "run: ''\n"
            "cases: ./c\n"
            "decision_field: d\n"
            "governing_types: []\n"
        )
        with pytest.raises(ConfigError, match="non-empty string"):
            KelvinConfig.load(write_yaml(tmp_path, bad))

    def test_governing_types_must_be_list_of_strings(self, tmp_path: Path) -> None:
        bad = (
            "run: cmd --input {input} --output {output}\n"
            "cases: ./c\n"
            "decision_field: d\n"
            "governing_types: [123, true]\n"
        )
        with pytest.raises(ConfigError, match="list of strings"):
            KelvinConfig.load(write_yaml(tmp_path, bad))

    def test_seed_must_be_int(self, tmp_path: Path) -> None:
        bad = (
            "run: cmd --input {input} --output {output}\n"
            "cases: ./c\n"
            "decision_field: d\n"
            "governing_types: []\n"
            "seed: not-a-number\n"
        )
        with pytest.raises(ConfigError, match="integer"):
            KelvinConfig.load(write_yaml(tmp_path, bad))


class TestSave:
    def test_roundtrip(self, tmp_path: Path) -> None:
        original = KelvinConfig(
            run="cmd --input {input} --output {output}",
            cases=Path("./ventures"),
            decision_field="recommendation",
            governing_types=["gate_rule", "policy_clause"],
            seed=7,
        )
        target = tmp_path / CONFIG_FILENAME
        original.save(target)
        reloaded = KelvinConfig.load(target)
        assert reloaded == original

    def test_save_writes_yaml_mapping(self, tmp_path: Path) -> None:
        cfg = KelvinConfig(
            run="cmd --input {input} --output {output}",
            cases=Path("./ventures"),
            decision_field="recommendation",
            governing_types=["gate_rule"],
            seed=0,
        )
        target = tmp_path / CONFIG_FILENAME
        cfg.save(target)
        data = yaml.safe_load(target.read_text(encoding="utf-8"))
        assert data["decision_field"] == "recommendation"
        assert data["governing_types"] == ["gate_rule"]
        assert data["seed"] == 0


class TestV03BackwardCompat:
    """v0.2 yaml must load under v0.3 with all new features disabled and
    default values matching v0.2 semantics.
    """

    def test_v02_yaml_loads_with_new_flags_off(self, tmp_path: Path) -> None:
        cfg = KelvinConfig.load(write_yaml(tmp_path, VALID_YAML))
        assert cfg.timeout_s == 150   # new default, bump from v0.2's hardcoded 60
        assert cfg.noise_floor.enabled is False
        assert cfg.counterfactual_swap.enabled is False
        assert cfg.intra_slot.enabled is False
        assert cfg.intra_slot.enabled_families == []

    def test_v02_yaml_save_roundtrip_does_not_emit_v03_keys(
        self, tmp_path: Path
    ) -> None:
        cfg = KelvinConfig.load(write_yaml(tmp_path, VALID_YAML))
        target = tmp_path / "out.yaml"
        cfg.save(target)
        data = yaml.safe_load(target.read_text(encoding="utf-8"))
        assert "noise_floor" not in data
        assert "counterfactual_swap" not in data
        assert "intra_slot" not in data

    def test_timeout_s_roundtrips_when_non_default(self, tmp_path: Path) -> None:
        yaml_text = VALID_YAML + "timeout_s: 300\n"
        cfg = KelvinConfig.load(write_yaml(tmp_path, yaml_text))
        assert cfg.timeout_s == 300
        target = tmp_path / "out.yaml"
        cfg.save(target)
        assert "timeout_s: 300" in target.read_text(encoding="utf-8")

    def test_timeout_s_rejects_non_positive(self, tmp_path: Path) -> None:
        yaml_text = VALID_YAML + "timeout_s: 0\n"
        with pytest.raises(ConfigError, match="timeout_s"):
            KelvinConfig.load(write_yaml(tmp_path, yaml_text))

    def test_timeout_s_rejects_bool(self, tmp_path: Path) -> None:
        yaml_text = VALID_YAML + "timeout_s: true\n"
        with pytest.raises(ConfigError, match="timeout_s"):
            KelvinConfig.load(write_yaml(tmp_path, yaml_text))


class TestNoiseFloorConfig:
    def test_accepts_valid_block(self, tmp_path: Path) -> None:
        yaml_text = VALID_YAML + "noise_floor:\n  enabled: true\n  replications: 7\n"
        cfg = KelvinConfig.load(write_yaml(tmp_path, yaml_text))
        assert cfg.noise_floor == NoiseFloorConfig(enabled=True, replications=7)

    def test_rejects_too_few_replications(self, tmp_path: Path) -> None:
        yaml_text = VALID_YAML + "noise_floor:\n  enabled: true\n  replications: 1\n"
        with pytest.raises(ConfigError, match="replications"):
            KelvinConfig.load(write_yaml(tmp_path, yaml_text))

    def test_rejects_non_bool_enabled(self, tmp_path: Path) -> None:
        yaml_text = VALID_YAML + 'noise_floor:\n  enabled: "yes"\n'
        with pytest.raises(ConfigError, match="noise_floor.enabled"):
            KelvinConfig.load(write_yaml(tmp_path, yaml_text))

    def test_rejects_non_mapping(self, tmp_path: Path) -> None:
        yaml_text = VALID_YAML + "noise_floor: true\n"
        with pytest.raises(ConfigError, match="noise_floor"):
            KelvinConfig.load(write_yaml(tmp_path, yaml_text))


class TestCounterfactualSwapConfig:
    def test_accepts_enabled_true(self, tmp_path: Path) -> None:
        yaml_text = VALID_YAML + "counterfactual_swap:\n  enabled: true\n"
        cfg = KelvinConfig.load(write_yaml(tmp_path, yaml_text))
        assert cfg.counterfactual_swap == CounterfactualSwapConfig(enabled=True)

    def test_rejects_non_bool(self, tmp_path: Path) -> None:
        yaml_text = VALID_YAML + 'counterfactual_swap:\n  enabled: "on"\n'
        with pytest.raises(ConfigError, match="counterfactual_swap.enabled"):
            KelvinConfig.load(write_yaml(tmp_path, yaml_text))


class TestIntraSlotConfig:
    def test_accepts_full_block(self, tmp_path: Path) -> None:
        yaml_text = (
            VALID_YAML
            + "intra_slot:\n"
            + "  enabled: true\n"
            + "  enabled_families:\n"
            + "    - irrelevant_paragraph_injection\n"
            + "    - numeric_magnitude\n"
            + "  filler_stripping_whitelist: [basically, just]\n"
        )
        cfg = KelvinConfig.load(write_yaml(tmp_path, yaml_text))
        assert cfg.intra_slot.enabled is True
        assert cfg.intra_slot.enabled_families == [
            "irrelevant_paragraph_injection",
            "numeric_magnitude",
        ]
        assert cfg.intra_slot.filler_stripping_whitelist == ["basically", "just"]

    def test_rejects_non_list_families(self, tmp_path: Path) -> None:
        yaml_text = VALID_YAML + "intra_slot:\n  enabled_families: irrelevant\n"
        with pytest.raises(ConfigError, match="enabled_families"):
            KelvinConfig.load(write_yaml(tmp_path, yaml_text))

    def test_rejects_non_string_family(self, tmp_path: Path) -> None:
        yaml_text = VALID_YAML + "intra_slot:\n  enabled_families: [1, 2]\n"
        with pytest.raises(ConfigError, match="enabled_families"):
            KelvinConfig.load(write_yaml(tmp_path, yaml_text))

    def test_defaults_when_block_omitted(self, tmp_path: Path) -> None:
        cfg = KelvinConfig.load(write_yaml(tmp_path, VALID_YAML))
        assert cfg.intra_slot == IntraSlotConfig()
