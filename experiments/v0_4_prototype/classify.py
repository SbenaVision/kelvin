#!/usr/bin/env python3
"""
v0.4 throwaway unitizer — paragraph-level, positional tags.

After SBA clarifications (April 26, 2026):
  - Level 1 (paragraphs) only — split on natural paragraph breaks (\\n\\n+)
  - Positional tags only (p1, p2, p3, ...) — no semantic vocabulary
  - Provider-abstracted Classifier interface in place (for future Level 2)
  - Anthropic is the first concrete provider implementation (not used by Level 1)
  - User-provided API key from env; never stored, logged, or transmitted

Level 1 is deterministic — no LLM call needed for paragraph splitting. The
provider-abstraction interface is wired so Level 2 (statements, requires LLM)
can plug in without re-architecting if Level 1 fails the throwaway.

THROWAWAY. No caching, no kelvin.yaml integration. Reads stripped prose from
stripped_cases/{case}.txt, writes labeled markdown to labeled_cases/{case}.md.

Usage:
  .venv/bin/python3 experiments/v0_4_prototype/classify.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Protocol


ROOT = Path(__file__).resolve().parent
STRIPPED_DIR = ROOT / "stripped_cases"
LABELED_DIR = ROOT / "labeled_cases"
LABELED_DIR.mkdir(exist_ok=True)


# ─── Classifier protocol (provider-agnostic interface from day one) ────────


class Classifier(Protocol):
    """Provider-agnostic unitizer interface.

    `unitize` takes raw prose and returns a list of (tag, content) tuples.
    Tags are positional (p1, p2, ...). Content is the raw text of the unit
    sliced from the source — the classifier never paraphrases or rewrites
    content, only identifies boundaries.
    """

    def unitize(self, prose: str) -> list[tuple[str, str]]: ...


class ParagraphUnitizer:
    """Level 1 unitizer — deterministic, no LLM call.

    Splits on `\\n\\n+` (paragraph boundaries). Tags positionally as
    p01, p02, ... Failed the throwaway gate (0/4 cases with above-noise
    units), Level 2 retry follows.
    """

    name = "paragraph_unitizer"

    def unitize(self, prose: str) -> list[tuple[str, str]]:
        paras = [p.strip() for p in re.split(r"\n\n+", prose) if p.strip()]
        return [(f"p{i + 1:02d}", p) for i, p in enumerate(paras)]


class SentenceUnitizer:
    """Level 2 unitizer — deterministic, no LLM call.

    Splits on sentence boundaries (`[.!?]\\s+(?=[A-Z])`) after collapsing
    intra-paragraph whitespace. Tags positionally as s01, s02, ... Each
    sentence becomes a unit. Tests whether finer-grained boundaries unblock
    per-unit signal where paragraph-level did not.
    """

    name = "sentence_unitizer"

    def unitize(self, prose: str) -> list[tuple[str, str]]:
        # Collapse paragraph breaks to spaces so we split on sentence boundaries
        # only. Preserves all content; just flattens layout.
        flat = re.sub(r"\s+", " ", prose).strip()
        # Split on . ! ? followed by whitespace + capital letter
        parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"\(])", flat)
        sentences = [p.strip() for p in parts if p.strip() and len(p.strip()) >= 10]
        return [(f"s{i + 1:02d}", s) for i, s in enumerate(sentences)]


# ─── LLM provider abstraction (Level 2 — deferred, stub only) ──────────────
# Kept as scaffolding so a Level 2 statement-level unitizer can plug in
# behind the same Classifier protocol without re-architecting the runner.
# Level 2 would call an LLM via one of these providers; Level 1 doesn't.

ENV_KEY_BY_PROVIDER = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai":    "OPENAI_API_KEY",
    "google":    "GOOGLE_API_KEY",
}


def get_provider_key(provider: str) -> str:
    """Read the user-provided API key from env. Never stored, never logged."""
    env_var = ENV_KEY_BY_PROVIDER.get(provider)
    if env_var is None:
        raise ValueError(f"Unknown provider: {provider}. Supported: {list(ENV_KEY_BY_PROVIDER)}")
    key = os.environ.get(env_var)
    if not key:
        raise RuntimeError(f"{env_var} is not set. Kelvin requires the user to provide their own key.")
    return key


# Concrete LLM classifier stubs — not used in the throwaway. Production v0.4
# implementations would inherit a common base class and plug in here.
class _AnthropicClassifierStub:
    """Reserved for Level 2 (statement-level unitization). Not implemented."""
    def __init__(self, model: str = "claude-haiku-4-5"):
        self.model = model

    def unitize(self, prose: str) -> list[tuple[str, str]]:
        raise NotImplementedError("Level 2 statement-level unitization is deferred to v0.4.x.")


# ─── Markdown reconstruction ────────────────────────────────────────────────


def render_labeled_md(units: list[tuple[str, str]]) -> str:
    """Render units as labeled markdown with `## p<N>` positional headers.

    The header carries no semantic content — its job is solely to introduce
    a structural cue for the downstream pipeline. Body is the original
    paragraph content, unchanged.
    """
    if not units:
        return ""
    parts = []
    for tag, content in units:
        parts.append(f"## {tag}\n\n{content}")
    return "\n\n".join(parts) + "\n"


# ─── Main ──────────────────────────────────────────────────────────────────


def main():
    # Level 2 retry — sentence-level after paragraph-level failed (0/4 above-noise).
    classifier: Classifier = SentenceUnitizer()
    cases = ["himom", "stagehand", "readyrounds", "narma"]
    summary = {}

    for case in cases:
        prose_path = STRIPPED_DIR / f"{case}.txt"
        if not prose_path.exists():
            print(f"  MISSING: {prose_path}")
            continue
        prose = prose_path.read_text(encoding="utf-8").strip()
        units = classifier.unitize(prose)
        print(f"=== {case} ({len(prose)} chars, {len(units)} units via {classifier.name}) ===")
        for tag, content in units:
            preview = content[:60].replace("\n", " ")
            print(f"  {tag}  {preview}...")

        labeled_md = render_labeled_md(units)
        out = LABELED_DIR / f"{case}.md"
        out.write_text(labeled_md, encoding="utf-8")
        (LABELED_DIR / f"{case}.classifier.json").write_text(
            json.dumps({
                "classifier": classifier.name,
                "level": 1,
                "n_units": len(units),
                "tags": [t for t, _ in units],
                "unit_lengths": [len(c) for _, c in units],
            }, indent=2),
            encoding="utf-8",
        )
        print(f"  wrote {out} ({len(labeled_md)} chars)")
        summary[case] = {"n_units": len(units), "tags": [t for t, _ in units]}

    print("\n=== SUMMARY ===")
    for c, s in summary.items():
        print(f"  {c}: {s}")


if __name__ == "__main__":
    main()
