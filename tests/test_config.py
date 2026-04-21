from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from kelvin.config import CONFIG_FILENAME, ConfigError, KelvinConfig

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
