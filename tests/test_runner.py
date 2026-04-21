from __future__ import annotations

import shlex
from pathlib import Path

from kelvin.runner import invoke


def _write_script(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def _template(script: Path) -> str:
    # shlex-quote the script path so spaces in tmp_path don't break the invocation.
    return f"python3 {shlex.quote(str(script))} --input {{input}} --output {{output}}"


BASE_PIPELINE = """\
import argparse, json, sys
ap = argparse.ArgumentParser()
ap.add_argument('--input')
ap.add_argument('--output')
args = ap.parse_args()
"""


class TestSuccess:
    def test_string_decision(self, tmp_path: Path) -> None:
        script = _write_script(
            tmp_path / "pipe.py",
            BASE_PIPELINE + "json.dump({'recommendation': 'approve'}, open(args.output, 'w'))\n",
        )
        result = invoke(
            _template(script),
            tmp_path / "in.md",
            tmp_path / "out.json",
            decision_field="recommendation",
        )
        assert result.ok
        assert result.decision_value == "approve"
        assert result.parsed_output == {"recommendation": "approve"}
        assert result.exit_code == 0
        assert result.error is None

    def test_numeric_decision(self, tmp_path: Path) -> None:
        script = _write_script(
            tmp_path / "pipe.py",
            BASE_PIPELINE + "json.dump({'score': 0.75}, open(args.output, 'w'))\n",
        )
        result = invoke(
            _template(script),
            tmp_path / "in.md",
            tmp_path / "out.json",
            decision_field="score",
        )
        assert result.ok
        assert result.decision_value == 0.75

    def test_pipeline_reads_input_path(self, tmp_path: Path) -> None:
        # Verify {input} placeholder substitution actually reaches the pipeline.
        script = _write_script(
            tmp_path / "pipe.py",
            BASE_PIPELINE
            + "content = open(args.input).read()\n"
            + "json.dump({'recommendation': content.strip()}, open(args.output, 'w'))\n",
        )
        input_path = tmp_path / "in.md"
        input_path.write_text("HELLO", encoding="utf-8")
        result = invoke(
            _template(script),
            input_path,
            tmp_path / "out.json",
            decision_field="recommendation",
        )
        assert result.ok
        assert result.decision_value == "HELLO"


class TestFailureModes:
    def test_non_zero_exit(self, tmp_path: Path) -> None:
        script = _write_script(
            tmp_path / "pipe.py",
            BASE_PIPELINE
            + "sys.stderr.write('something broke\\n')\n"
            + "sys.exit(3)\n",
        )
        result = invoke(
            _template(script),
            tmp_path / "in.md",
            tmp_path / "out.json",
            decision_field="recommendation",
        )
        assert not result.ok
        assert result.exit_code == 3
        assert "non-zero exit" in (result.error or "")
        assert "something broke" in (result.stderr_tail or "")

    def test_missing_output_file(self, tmp_path: Path) -> None:
        script = _write_script(
            tmp_path / "pipe.py",
            BASE_PIPELINE + "pass  # exit 0 without writing output\n",
        )
        result = invoke(
            _template(script),
            tmp_path / "in.md",
            tmp_path / "out.json",
            decision_field="recommendation",
        )
        assert not result.ok
        assert "output file not created" in (result.error or "")

    def test_invalid_json(self, tmp_path: Path) -> None:
        script = _write_script(
            tmp_path / "pipe.py",
            BASE_PIPELINE + "open(args.output, 'w').write('not really json {')\n",
        )
        result = invoke(
            _template(script),
            tmp_path / "in.md",
            tmp_path / "out.json",
            decision_field="recommendation",
        )
        assert not result.ok
        assert "not valid JSON" in (result.error or "")

    def test_non_dict_json(self, tmp_path: Path) -> None:
        # Top-level array, not object.
        script = _write_script(
            tmp_path / "pipe.py",
            BASE_PIPELINE + "json.dump([1, 2, 3], open(args.output, 'w'))\n",
        )
        result = invoke(
            _template(script),
            tmp_path / "in.md",
            tmp_path / "out.json",
            decision_field="recommendation",
        )
        assert not result.ok
        assert "mapping" in (result.error or "")

    def test_missing_decision_field(self, tmp_path: Path) -> None:
        script = _write_script(
            tmp_path / "pipe.py",
            BASE_PIPELINE
            + "json.dump({'other': 'value', 'narrative': 'x'}, open(args.output, 'w'))\n",
        )
        result = invoke(
            _template(script),
            tmp_path / "in.md",
            tmp_path / "out.json",
            decision_field="recommendation",
        )
        assert not result.ok
        assert "recommendation" in (result.error or "")
        # Actual keys listed so the user can diagnose:
        assert "narrative" in (result.error or "")
        # parsed_output is populated so the orchestrator can distinguish this
        # failure kind from a pipeline crash.
        assert result.parsed_output == {"other": "value", "narrative": "x"}


class TestQuoting:
    def test_path_with_spaces_survives_substitution(self, tmp_path: Path) -> None:
        space_dir = tmp_path / "with spaces"
        space_dir.mkdir()
        script = _write_script(
            space_dir / "pipe.py",
            BASE_PIPELINE
            + "json.dump({'recommendation': 'ok'}, open(args.output, 'w'))\n",
        )
        input_path = space_dir / "in put.md"
        input_path.write_text("x", encoding="utf-8")
        result = invoke(
            _template(script),
            input_path,
            space_dir / "out put.json",
            decision_field="recommendation",
        )
        assert result.ok
        assert result.decision_value == "ok"
