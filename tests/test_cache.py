"""Tests for the opt-in on-disk invocation cache.

The cache lives in `kelvin/runner.py` and is keyed by
`sha256(run_template + rendered_markdown + decision_field)`. These tests use
a "counter pipeline" — a shell script that appends a line to a tracking
file every time it runs — so cache hits can be observed as no change to the
tracking file rather than by mocking the subprocess.
"""

from __future__ import annotations

import json
import shlex
import stat
from pathlib import Path

import pytest

from kelvin.config import KelvinConfig
from kelvin.runner import invoke

# ─── Fixtures ───────────────────────────────────────────────────────────────


def _write_counter_pipeline(tmp_path: Path, decision: str = "approve") -> tuple[Path, Path]:
    """Install a pipeline script that counts invocations by appending to a
    file. Returns (script_path, counter_path).
    """
    counter = tmp_path / "counter.log"
    counter.write_text("", encoding="utf-8")
    script = tmp_path / "counter_pipe.sh"
    script.write_text(
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        "input=\"\"\n"
        "output=\"\"\n"
        "while [ $# -gt 0 ]; do\n"
        "  case \"$1\" in\n"
        "    --input) input=\"$2\"; shift 2;;\n"
        "    --output) output=\"$2\"; shift 2;;\n"
        "    *) shift;;\n"
        "  esac\n"
        "done\n"
        f"echo invoked >> {shlex.quote(str(counter))}\n"
        f"printf '%s' '{{\"recommendation\": \"{decision}\"}}' > \"$output\"\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script, counter


def _run_template(script: Path) -> str:
    return f"bash {shlex.quote(str(script))} --input {{input}} --output {{output}}"


def _call_count(counter: Path) -> int:
    return sum(1 for _ in counter.read_text(encoding="utf-8").splitlines())


def _render(tmp_path: Path, name: str, markdown: str) -> Path:
    p = tmp_path / f"{name}.md"
    p.write_text(markdown, encoding="utf-8")
    return p


# ─── Cache key behavior ─────────────────────────────────────────────────────


class TestCacheHit:
    def test_second_call_is_a_hit_when_inputs_match(self, tmp_path: Path) -> None:
        script, counter = _write_counter_pipeline(tmp_path)
        cache = tmp_path / "cache"
        inp = _render(tmp_path, "case", "## Interview\nSame body.\n")
        out = tmp_path / "out.json"

        r1 = invoke(_run_template(script), inp, out, "recommendation", cache_dir=cache)
        r2 = invoke(_run_template(script), inp, out, "recommendation", cache_dir=cache)

        assert r1.ok is True and r2.ok is True
        assert r1.decision_value == r2.decision_value == "approve"
        assert _call_count(counter) == 1, "second call should have been a cache hit"

    def test_cache_hit_materializes_output_file(self, tmp_path: Path) -> None:
        # Downstream tools diff output.json; a hit must leave one on disk.
        script, counter = _write_counter_pipeline(tmp_path, decision="reject")
        cache = tmp_path / "cache"
        inp = _render(tmp_path, "case", "## Interview\nBody.\n")
        out = tmp_path / "out.json"

        invoke(_run_template(script), inp, out, "recommendation", cache_dir=cache)
        out.unlink()  # wipe; force the hit to recreate it
        assert not out.exists()

        r = invoke(_run_template(script), inp, out, "recommendation", cache_dir=cache)
        assert r.ok is True
        assert out.exists()
        assert json.loads(out.read_text())["recommendation"] == "reject"
        assert _call_count(counter) == 1

    def test_cache_entry_written_to_disk(self, tmp_path: Path) -> None:
        script, _ = _write_counter_pipeline(tmp_path)
        cache = tmp_path / "cache"
        inp = _render(tmp_path, "case", "## Interview\nBody.\n")
        out = tmp_path / "out.json"

        invoke(_run_template(script), inp, out, "recommendation", cache_dir=cache)
        files = list(cache.glob("*.json"))
        assert len(files) == 1
        entry = json.loads(files[0].read_text())
        assert entry["schema_version"] == 1
        assert entry["result"]["ok"] is True
        assert entry["result"]["decision_value"] == "approve"


class TestCacheKeyDiscrimination:
    def test_different_markdown_is_a_miss(self, tmp_path: Path) -> None:
        script, counter = _write_counter_pipeline(tmp_path)
        cache = tmp_path / "cache"
        out = tmp_path / "out.json"
        inp_a = _render(tmp_path, "a", "## Interview\nFirst body.\n")
        inp_b = _render(tmp_path, "b", "## Interview\nSecond body.\n")

        invoke(_run_template(script), inp_a, out, "recommendation", cache_dir=cache)
        invoke(_run_template(script), inp_b, out, "recommendation", cache_dir=cache)
        assert _call_count(counter) == 2

    def test_different_decision_field_is_a_miss(self, tmp_path: Path) -> None:
        # Stick the same value under two field names; decision_field is part
        # of the key so the second lookup must miss.
        script = tmp_path / "twokeys.sh"
        counter = tmp_path / "counter.log"
        counter.write_text("", encoding="utf-8")
        script.write_text(
            "#!/bin/bash\n"
            "set -euo pipefail\n"
            "while [ $# -gt 0 ]; do\n"
            "  case \"$1\" in\n"
            "    --input) shift 2;;\n"
            "    --output) output=\"$2\"; shift 2;;\n"
            "    *) shift;;\n"
            "  esac\n"
            "done\n"
            f"echo invoked >> {shlex.quote(str(counter))}\n"
            "printf '%s' '{\"recommendation\": \"approve\", \"score\": 1}' > \"$output\"\n",
            encoding="utf-8",
        )
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        cache = tmp_path / "cache"
        inp = _render(tmp_path, "case", "## Interview\nBody.\n")
        out = tmp_path / "out.json"

        invoke(_run_template(script), inp, out, "recommendation", cache_dir=cache)
        invoke(_run_template(script), inp, out, "score", cache_dir=cache)
        assert _call_count(counter) == 2

    def test_different_run_template_is_a_miss(self, tmp_path: Path) -> None:
        script, counter = _write_counter_pipeline(tmp_path)
        cache = tmp_path / "cache"
        inp = _render(tmp_path, "case", "## Interview\nBody.\n")
        out = tmp_path / "out.json"

        base = _run_template(script)
        # Same pipeline, two different command strings — appending a no-op
        # flag the script ignores. The templates differ as strings, so the
        # cache key differs, so the second invocation must miss.
        invoke(base, inp, out, "recommendation", cache_dir=cache)
        invoke(base + " --tag x", inp, out, "recommendation", cache_dir=cache)
        assert _call_count(counter) == 2


# ─── Edge cases ─────────────────────────────────────────────────────────────


class TestCacheEdgeCases:
    def test_cache_disabled_when_dir_is_none(self, tmp_path: Path) -> None:
        script, counter = _write_counter_pipeline(tmp_path)
        inp = _render(tmp_path, "case", "## Interview\nBody.\n")
        out = tmp_path / "out.json"

        invoke(_run_template(script), inp, out, "recommendation", cache_dir=None)
        invoke(_run_template(script), inp, out, "recommendation", cache_dir=None)
        assert _call_count(counter) == 2
        # No cache directory should have been created anywhere.
        assert not (tmp_path / "cache").exists()

    def test_corrupt_cache_entry_is_treated_as_miss(self, tmp_path: Path) -> None:
        script, counter = _write_counter_pipeline(tmp_path)
        cache = tmp_path / "cache"
        cache.mkdir()
        inp = _render(tmp_path, "case", "## Interview\nBody.\n")
        out = tmp_path / "out.json"

        # Seed the cache with junk. The exact filename doesn't matter — a
        # real key will differ — but a corrupt entry anywhere in the dir
        # shouldn't break the miss path.
        invoke(_run_template(script), inp, out, "recommendation", cache_dir=cache)
        entry_path = next(cache.glob("*.json"))
        entry_path.write_text("{not valid json", encoding="utf-8")

        invoke(_run_template(script), inp, out, "recommendation", cache_dir=cache)
        assert _call_count(counter) == 2

    def test_cache_does_not_store_failures(self, tmp_path: Path) -> None:
        # Pipeline exits non-zero every call; nothing should be cached and
        # every invocation should run fresh.
        script = tmp_path / "fail.sh"
        counter = tmp_path / "counter.log"
        counter.write_text("", encoding="utf-8")
        script.write_text(
            "#!/bin/bash\n"
            f"echo invoked >> {shlex.quote(str(counter))}\n"
            "exit 1\n",
            encoding="utf-8",
        )
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        cache = tmp_path / "cache"
        inp = _render(tmp_path, "case", "## Interview\nBody.\n")
        out = tmp_path / "out.json"

        r1 = invoke(_run_template(script), inp, out, "recommendation", cache_dir=cache)
        r2 = invoke(_run_template(script), inp, out, "recommendation", cache_dir=cache)
        assert r1.ok is False and r2.ok is False
        assert _call_count(counter) == 2
        # No cache entry was ever written.
        assert not cache.exists() or not any(cache.glob("*.json"))


# ─── Config integration ─────────────────────────────────────────────────────


class TestConfigCacheDir:
    def test_cache_dir_parsed_from_yaml(self, tmp_path: Path) -> None:
        p = tmp_path / "kelvin.yaml"
        p.write_text(
            "run: cmd --input {input} --output {output}\n"
            "cases: ./cases\n"
            "decision_field: recommendation\n"
            "governing_types: [gate_rule]\n"
            "cache_dir: .kelvin-cache\n",
            encoding="utf-8",
        )
        cfg = KelvinConfig.load(p)
        assert cfg.cache_dir == Path(".kelvin-cache")

    def test_missing_cache_dir_means_disabled(self, tmp_path: Path) -> None:
        p = tmp_path / "kelvin.yaml"
        p.write_text(
            "run: cmd --input {input} --output {output}\n"
            "cases: ./cases\n"
            "decision_field: recommendation\n"
            "governing_types: [gate_rule]\n",
            encoding="utf-8",
        )
        cfg = KelvinConfig.load(p)
        assert cfg.cache_dir is None

    def test_bad_cache_dir_type_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "kelvin.yaml"
        p.write_text(
            "run: cmd --input {input} --output {output}\n"
            "cases: ./cases\n"
            "decision_field: recommendation\n"
            "governing_types: [gate_rule]\n"
            "cache_dir: 42\n",
            encoding="utf-8",
        )
        from kelvin.config import ConfigError
        with pytest.raises(ConfigError, match="cache_dir"):
            KelvinConfig.load(p)

    def test_save_roundtrip_preserves_cache_dir(self, tmp_path: Path) -> None:
        p = tmp_path / "kelvin.yaml"
        cfg = KelvinConfig(
            run="cmd --input {input} --output {output}",
            cases=Path("./cases"),
            decision_field="rec",
            governing_types=["gate_rule"],
            cache_dir=Path(".cache"),
        )
        cfg.save(p)
        loaded = KelvinConfig.load(p)
        assert loaded.cache_dir == Path(".cache")

    def test_save_omits_cache_dir_when_none(self, tmp_path: Path) -> None:
        p = tmp_path / "kelvin.yaml"
        cfg = KelvinConfig(
            run="cmd --input {input} --output {output}",
            cases=Path("./cases"),
            decision_field="rec",
            governing_types=["gate_rule"],
        )
        cfg.save(p)
        assert "cache_dir" not in p.read_text(encoding="utf-8")


# ─── End-to-end via run_check ───────────────────────────────────────────────


class TestCacheEndToEnd:
    def test_second_run_reuses_cache(self, tmp_path: Path) -> None:
        """A second full `run_check` invocation should reuse Phase 1 and
        Phase 2 entries so the counter pipeline fires far fewer times."""
        from kelvin.check import run_check

        script, counter = _write_counter_pipeline(tmp_path)
        cases_dir = tmp_path / "cases"
        cases_dir.mkdir()
        (cases_dir / "a.md").write_text(
            "## Interview\nA.\n\n## Gate Rule\nA_G1.\n", encoding="utf-8"
        )
        (cases_dir / "b.md").write_text(
            "## Interview\nB.\n\n## Gate Rule\nB_G1.\n", encoding="utf-8"
        )

        cfg = KelvinConfig(
            run=_run_template(script),
            cases=cases_dir,
            decision_field="recommendation",
            governing_types=["gate_rule"],
            seed=0,
            cache_dir=tmp_path / ".kelvin-cache",
        )
        cfg.save(tmp_path / "kelvin.yaml")

        run_check(tmp_path, echo=lambda _s: None)
        first = _call_count(counter)
        assert first > 0

        # Wipe run outputs but keep the cache.
        import shutil

        shutil.rmtree(tmp_path / "kelvin")
        run_check(tmp_path, echo=lambda _s: None)
        second = _call_count(counter) - first

        # Every invocation in the second run should have been a cache hit.
        assert second == 0, (
            f"expected all cache hits on second run, got {second} fresh invocations"
        )
