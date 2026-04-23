"""Tests for the forecast dialog — the y/n prompt added via --confirm.

Both --yes and non-TTY stdin independently bypass the prompt (CI safety).
Default (no --confirm) preserves v0.2 behavior: no prompt at all.
"""

from __future__ import annotations

import pytest

from kelvin.check import _accept_forecast


class TestBypassConditions:
    def test_auto_accept_bypasses_prompt(self) -> None:
        # --yes short-circuits regardless of TTY state.
        called: list[str] = []
        assert _accept_forecast(
            auto_accept=True,
            input_fn=lambda prompt: called.append(prompt) or "n",
            isatty=lambda: True,
        ) is True
        assert called == []  # prompt was never shown

    def test_non_tty_stdin_bypasses_prompt(self) -> None:
        # CI safety: when stdin is not a TTY, auto-accept without prompting.
        called: list[str] = []
        assert _accept_forecast(
            auto_accept=False,
            input_fn=lambda prompt: called.append(prompt) or "n",
            isatty=lambda: False,
        ) is True
        assert called == []  # prompt was never shown

    def test_both_bypasses_active_together(self) -> None:
        # --yes AND non-TTY stdin — still accept.
        assert _accept_forecast(
            auto_accept=True,
            input_fn=lambda prompt: "n",
            isatty=lambda: False,
        ) is True


class TestInteractivePrompt:
    def test_y_accepts(self) -> None:
        assert _accept_forecast(
            auto_accept=False,
            input_fn=lambda prompt: "y",
            isatty=lambda: True,
        ) is True

    def test_yes_accepts(self) -> None:
        assert _accept_forecast(
            auto_accept=False,
            input_fn=lambda prompt: "yes",
            isatty=lambda: True,
        ) is True

    def test_Y_case_insensitive(self) -> None:
        assert _accept_forecast(
            auto_accept=False,
            input_fn=lambda prompt: "Y",
            isatty=lambda: True,
        ) is True

    def test_yes_with_whitespace(self) -> None:
        assert _accept_forecast(
            auto_accept=False,
            input_fn=lambda prompt: "  yes  ",
            isatty=lambda: True,
        ) is True

    def test_n_rejects(self) -> None:
        assert _accept_forecast(
            auto_accept=False,
            input_fn=lambda prompt: "n",
            isatty=lambda: True,
        ) is False

    def test_empty_response_rejects(self) -> None:
        # Default N: pressing enter = no.
        assert _accept_forecast(
            auto_accept=False,
            input_fn=lambda prompt: "",
            isatty=lambda: True,
        ) is False

    def test_random_text_rejects(self) -> None:
        assert _accept_forecast(
            auto_accept=False,
            input_fn=lambda prompt: "maybe",
            isatty=lambda: True,
        ) is False

    def test_eof_rejects(self) -> None:
        # Broken pipe / stdin closed mid-prompt — reject, don't hang or accept.
        def raise_eof(prompt: str) -> str:
            raise EOFError()
        assert _accept_forecast(
            auto_accept=False,
            input_fn=raise_eof,
            isatty=lambda: True,
        ) is False


class TestPromptTextIsShown:
    def test_prompt_text_passed_to_input_fn(self) -> None:
        captured: list[str] = []

        def fake_input(prompt: str) -> str:
            captured.append(prompt)
            return "y"

        _accept_forecast(
            auto_accept=False,
            input_fn=fake_input,
            isatty=lambda: True,
        )
        assert len(captured) == 1
        assert "[y/N]" in captured[0]
