"""Tests for the v0.4 CLI surface (version, --verbose, --research,
--report-format)."""

from __future__ import annotations

from typer.testing import CliRunner

from kelvin import __version__
from kelvin.cli import app

runner = CliRunner()


# ── --version ────────────────────────────────────────────────────────────

def test_version_flag_emits_version_and_exits():
    r = runner.invoke(app, ["--version"])
    assert r.exit_code == 0
    assert __version__ in r.output


# ── --report-format validation ────────────────────────────────────────────

def test_report_format_invalid_value_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["check", "--report-format", "yaml"])
    assert r.exit_code == 1
    assert "must be one of" in r.output or "report-format" in r.output


# ── --research is mutually exclusive with --report-format=json|markdown ──

def test_research_with_report_format_json_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(
        app, ["check", "--research", "--report-format", "json"]
    )
    assert r.exit_code == 1
    assert "mutually exclusive" in r.output.lower()


def test_research_with_report_format_markdown_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(
        app, ["check", "--research", "--report-format", "markdown"]
    )
    assert r.exit_code == 1


# ── --research with default practitioner format is allowed ───────────────

def test_research_with_default_format_allowed(tmp_path, monkeypatch):
    """The combination shouldn't error on the flag-validation layer.
    (It will still fail because there's no kelvin.yaml — that's fine
    here; we just want to ensure flag validation passes.)"""
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["check", "--research"])
    # Without kelvin.yaml the run errors out, but exit code 1 with
    # "config" in the message, NOT "mutually exclusive".
    assert "mutually exclusive" not in r.output.lower()
