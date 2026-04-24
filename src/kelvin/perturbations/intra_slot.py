"""Pillar 3 perturbation generators (v0.3 reframe).

Seven rule-based families — four invariance (presentation-layer) and
three sensitivity (mechanical edits on governing content). The original
v0.3 Pillar 3 scope included rhetorical families (hedges, intensifiers,
discourse markers) that required labeling-study validation because
rule-based construction cannot guarantee pragmatic meaning-preservation
on those operators. That scope was cut; the families in this module
all have invariants that are trivially true by construction — no
labeling study, no judge model, no semantic gymnastics.

### Invariance families (presentation-layer)

- `WhitespaceJitterGenerator` — inserts blank lines, adds trailing
  whitespace, duplicates blank-line separators. Preserves every token
  verbatim; only surface whitespace layout changes.
- `PunctuationNormalizeGenerator` — swaps curly quotes → straight,
  em-dash → double-hyphen (or vice versa), canonicalizes ellipses.
  No semantic content; only orthographic normalization.
- `BulletReformatGenerator` — changes list markers (`-` ↔ `*`, `1.`
  ↔ `1)`) in any enumerations. No semantic content.
- `NonGoverningDuplicationGenerator` — duplicates a sentence verbatim
  from a non-governing section. Truth-conditional meaning is preserved
  by construction: the sentence was already in the document.

### Sensitivity families (mechanical, governing-section targeted)

- `NumericMagnitudeGenerator` — multiplies numbers in a governing
  section by {2, 5, 10, 100}. Four variants per case, ranked as a
  sensitivity curve.
- `ComparatorFlipGenerator` — swaps comparators from a closed,
  validated pair list (`at least` ↔ `at most`, `more than` ↔ `less
  than`, etc.) in a governing section.
- `PolarityFlipGenerator` — swaps polarity words from a closed,
  validated antonym list (`approved` ↔ `denied`, `committed` ↔
  `withdrawn`, etc.) in a governing section.

All seven generators gate on `cfg.intra_slot.enabled` AND on the
family name appearing in `cfg.intra_slot.enabled_families`. Default
off: v0.2.1 yaml files produce zero Pillar 3 perturbations.
"""

from __future__ import annotations

import re

from kelvin.parser import render_case
from kelvin.perturbations import rng_for
from kelvin.types import Case, Perturbation, PerturbationBatch, Unit


# ─── Shared utilities ─────────────────────────────────────────────────────


def _split_sentences(body: str) -> list[str]:
    """Split a section body into sentences on period-space boundaries.

    Intentionally coarse — doesn't handle abbreviations. Good enough for
    the presentation-layer duplicators, which don't depend on sentence
    boundaries carrying semantic meaning.
    """
    out: list[str] = []
    for raw in re.split(r"(?<=[.!?])\s+", body.strip()):
        s = raw.strip()
        if s:
            out.append(s)
    return out


# ─── Invariance: whitespace jitter ────────────────────────────────────────


class WhitespaceJitterGenerator:
    """Adds/removes blank-line separators and trailing whitespace.

    Preserves token content verbatim. Three variants per case, each with
    a different jitter pattern.
    """

    kind = "whitespace_jitter"
    FAMILY_NAME = "whitespace_jitter"
    TARGET_COUNT = 3

    def generate(
        self,
        case: Case,
        peer_cases: list[Case],
        *,
        seed: int,
        governing_types: list[str],
    ) -> PerturbationBatch:
        rng = rng_for(seed, "whitespace_jitter", case.name)
        perturbations: list[Perturbation] = []
        for i in range(self.TARGET_COUNT):
            new_units: list[Unit] = []
            for u in case.units:
                # Variant patterns: add trailing newlines, double-space
                # paragraphs, inject blank lines. All whitespace-only.
                body = u.content
                mode = rng.randint(0, 2)
                if mode == 0:
                    # Double up internal blank lines.
                    body = re.sub(r"\n\n+", "\n\n\n", body)
                elif mode == 1:
                    # Add trailing whitespace to random paragraphs.
                    lines = body.split("\n")
                    for j in range(len(lines)):
                        if lines[j] and rng.random() < 0.3:
                            lines[j] = lines[j] + "  "
                    body = "\n".join(lines)
                else:
                    # Add leading blank before the body.
                    body = "\n" + body
                new_units.append(
                    Unit(
                        type=u.type,
                        content=body,
                        raw_header=u.raw_header,
                        index=u.index,
                    )
                )
            perturbations.append(
                Perturbation(
                    case_name=case.name,
                    kind="whitespace_jitter",
                    variant_id=f"whitespace_jitter-{i + 1:02d}",
                    rendered_markdown=render_case(case.preamble, new_units),
                    notes={"variant": i},
                )
            )
        return PerturbationBatch(perturbations=perturbations)


# ─── Invariance: punctuation normalize ────────────────────────────────────


_PUNCT_SWAPS: tuple[tuple[str, str], ...] = (
    ("\u201c", '"'),   # left curly double quote → straight
    ("\u201d", '"'),   # right curly double quote → straight
    ("\u2018", "'"),   # left curly single quote → straight
    ("\u2019", "'"),   # right curly single quote → straight
    ("\u2014", "--"),  # em-dash → double-hyphen
    ("\u2013", "-"),   # en-dash → hyphen
    ("\u2026", "..."), # ellipsis → three periods
)


class PunctuationNormalizeGenerator:
    """Swaps curly quotes, em/en dashes, and ellipsis to ASCII
    equivalents (or back). Purely orthographic."""

    kind = "punctuation_normalize"
    FAMILY_NAME = "punctuation_normalize"
    TARGET_COUNT = 3

    def generate(
        self,
        case: Case,
        peer_cases: list[Case],
        *,
        seed: int,
        governing_types: list[str],
    ) -> PerturbationBatch:
        rng = rng_for(seed, "punctuation_normalize", case.name)
        perturbations: list[Perturbation] = []
        for i in range(self.TARGET_COUNT):
            # Variant 0: ASCII-ify. Variant 1: reverse-direction (ASCII →
            # curly/em-dash). Variant 2: mixed partial.
            new_units: list[Unit] = []
            for u in case.units:
                body = u.content
                if i == 0:
                    for src, dst in _PUNCT_SWAPS:
                        body = body.replace(src, dst)
                elif i == 1:
                    # Reverse: ASCII → fancy
                    body = body.replace('"', "\u201c").replace("--", "\u2014")
                    body = body.replace("...", "\u2026")
                else:
                    # Random subset of forward swaps.
                    subset_size = max(1, rng.randint(1, len(_PUNCT_SWAPS) - 1))
                    chosen = rng.sample(_PUNCT_SWAPS, subset_size)
                    for src, dst in chosen:
                        body = body.replace(src, dst)
                new_units.append(
                    Unit(
                        type=u.type,
                        content=body,
                        raw_header=u.raw_header,
                        index=u.index,
                    )
                )
            perturbations.append(
                Perturbation(
                    case_name=case.name,
                    kind="punctuation_normalize",
                    variant_id=f"punctuation_normalize-{i + 1:02d}",
                    rendered_markdown=render_case(case.preamble, new_units),
                    notes={"variant": i},
                )
            )
        return PerturbationBatch(perturbations=perturbations)


# ─── Invariance: bullet reformat ──────────────────────────────────────────


class BulletReformatGenerator:
    """Swaps bullet-style list markers `-` ↔ `*` and ordered-list styles
    `1.` ↔ `1)`. No semantic content changed."""

    kind = "bullet_reformat"
    FAMILY_NAME = "bullet_reformat"
    TARGET_COUNT = 2

    def generate(
        self,
        case: Case,
        peer_cases: list[Case],
        *,
        seed: int,
        governing_types: list[str],
    ) -> PerturbationBatch:
        rng = rng_for(seed, "bullet_reformat", case.name)
        perturbations: list[Perturbation] = []
        for i in range(self.TARGET_COUNT):
            new_units: list[Unit] = []
            for u in case.units:
                body = u.content
                if i == 0:
                    body = re.sub(r"^- ", "* ", body, flags=re.MULTILINE)
                    body = re.sub(r"^(\d+)\. ", r"\1) ", body, flags=re.MULTILINE)
                else:
                    body = re.sub(r"^\* ", "- ", body, flags=re.MULTILINE)
                    body = re.sub(r"^(\d+)\) ", r"\1. ", body, flags=re.MULTILINE)
                new_units.append(
                    Unit(
                        type=u.type,
                        content=body,
                        raw_header=u.raw_header,
                        index=u.index,
                    )
                )
            perturbations.append(
                Perturbation(
                    case_name=case.name,
                    kind="bullet_reformat",
                    variant_id=f"bullet_reformat-{i + 1:02d}",
                    rendered_markdown=render_case(case.preamble, new_units),
                    notes={"variant": i},
                )
            )
        return PerturbationBatch(perturbations=perturbations)


# ─── Invariance: non-governing sentence duplication ───────────────────────


class NonGoverningDuplicationGenerator:
    """Duplicates a sentence verbatim inside a non-governing section.

    Truth-conditional meaning is preserved by construction: the sentence
    was already in the document; repeating it adds no new claim. A
    pipeline that interprets repetition as rhetorical emphasis may still
    shift — that's a legitimate diagnostic signal, not a false positive.
    """

    kind = "non_governing_duplication"
    FAMILY_NAME = "non_governing_duplication"
    TARGET_COUNT = 3

    def generate(
        self,
        case: Case,
        peer_cases: list[Case],
        *,
        seed: int,
        governing_types: list[str],
    ) -> PerturbationBatch:
        # Non-governing = sections whose type is not in governing_types.
        non_gov_units = [u for u in case.units if u.type not in governing_types]
        if not non_gov_units:
            return PerturbationBatch(
                perturbations=[],
                warnings=[
                    f"{case.name}: non_governing_duplication skipped — all "
                    f"sections are governing types"
                ],
            )

        rng = rng_for(seed, "non_governing_duplication", case.name)
        perturbations: list[Perturbation] = []
        for i in range(self.TARGET_COUNT):
            # Pick a non-governing unit whose body has ≥1 sentence.
            candidates = [u for u in non_gov_units if _split_sentences(u.content)]
            if not candidates:
                break
            target = rng.choice(candidates)
            sentences = _split_sentences(target.content)
            chosen_idx = rng.randrange(len(sentences))
            chosen = sentences[chosen_idx]

            # Insert a duplicate immediately after the chosen sentence.
            new_sentences = list(sentences)
            new_sentences.insert(chosen_idx + 1, chosen)
            new_body = " ".join(new_sentences)

            new_units: list[Unit] = []
            for u in case.units:
                if u.index == target.index:
                    new_units.append(
                        Unit(
                            type=u.type,
                            content=new_body,
                            raw_header=u.raw_header,
                            index=u.index,
                        )
                    )
                else:
                    new_units.append(u)

            perturbations.append(
                Perturbation(
                    case_name=case.name,
                    kind="non_governing_duplication",
                    variant_id=f"non_governing_duplication-{i + 1:02d}",
                    rendered_markdown=render_case(case.preamble, new_units),
                    notes={
                        "target_section": target.type,
                        "duplicated_sentence": chosen,
                        "sentence_index": chosen_idx,
                    },
                )
            )
        return PerturbationBatch(perturbations=perturbations)


# ─── Sensitivity: numeric magnitude ───────────────────────────────────────


_NUMERIC_RE = re.compile(r"(?<![\w\-])(\d+(?:\.\d+)?)(?!\w)")


class NumericMagnitudeGenerator:
    """Multiplies numbers in governing sections by {2, 5, 10, 100}.

    Four variants per case per governing type, rendered as a sensitivity
    curve. An evidence-tracking pipeline should move its decision more
    sharply at higher magnitudes.
    """

    kind = "numeric_magnitude"
    FAMILY_NAME = "numeric_magnitude"
    MULTIPLIERS: tuple[int, ...] = (2, 5, 10, 100)

    def generate(
        self,
        case: Case,
        peer_cases: list[Case],
        *,
        seed: int,
        governing_types: list[str],
    ) -> PerturbationBatch:
        warnings: list[str] = []
        perturbations: list[Perturbation] = []

        for gtype in governing_types:
            gov_units = case.units_of_type(gtype)
            if not gov_units:
                warnings.append(
                    f"{case.name}: numeric_magnitude skipped for {gtype} — "
                    f"case has no units of this type"
                )
                continue

            for target in gov_units:
                numbers = list(_NUMERIC_RE.finditer(target.content))
                if not numbers:
                    warnings.append(
                        f"{case.name}: numeric_magnitude for {gtype} unit "
                        f"at index {target.index} — no numeric tokens found"
                    )
                    continue

                for mult in self.MULTIPLIERS:
                    new_content = _apply_numeric_multiplier(target.content, mult)
                    new_units = [
                        (
                            Unit(
                                type=u.type,
                                content=new_content,
                                raw_header=u.raw_header,
                                index=u.index,
                            )
                            if u.index == target.index
                            else u
                        )
                        for u in case.units
                    ]
                    perturbations.append(
                        Perturbation(
                            case_name=case.name,
                            kind="numeric_magnitude",
                            variant_id=f"numeric_magnitude-{gtype}-x{mult:03d}",
                            rendered_markdown=render_case(case.preamble, new_units),
                            notes={
                                "governing_type": gtype,
                                "position_modified": target.index,
                                "multiplier": mult,
                                "n_numbers_modified": len(numbers),
                            },
                        )
                    )
        return PerturbationBatch(perturbations=perturbations, warnings=warnings)


def _apply_numeric_multiplier(text: str, mult: int) -> str:
    def repl(m: re.Match) -> str:
        s = m.group(1)
        if "." in s:
            val = float(s) * mult
            return f"{val:g}"
        return str(int(s) * mult)

    return _NUMERIC_RE.sub(repl, text)


# ─── Sensitivity: comparator flip ─────────────────────────────────────────
#
# Hand-validated bidirectional pair list. Each pair swaps both ways: if
# "at least" is in the text, it becomes "at most", and a separate
# perturbation swaps "at most" → "at least". Selection is longest-match
# first so "no more than" takes precedence over "more than".

_COMPARATOR_PAIRS: tuple[tuple[str, str], ...] = (
    ("at least", "at most"),
    ("no more than", "no less than"),
    ("no less than", "no more than"),
    ("more than", "less than"),
    ("less than", "more than"),
    ("greater than", "less than"),
    ("fewer than", "more than"),
    ("above", "below"),
    ("over", "under"),
    ("exceeds", "falls short of"),
)


def _swap_comparators(text: str) -> tuple[str, int]:
    """Returns (new_text, n_swaps). Longest-match-first, case-insensitive."""
    pairs = sorted(_COMPARATOR_PAIRS, key=lambda p: -len(p[0]))
    swaps = 0
    out = text
    for src, dst in pairs:
        pattern = re.compile(r"\b" + re.escape(src) + r"\b", re.IGNORECASE)
        new_out, n = pattern.subn(dst, out)
        if n > 0:
            out = new_out
            swaps += n
    return out, swaps


class ComparatorFlipGenerator:
    """Swaps closed-list comparators within governing sections."""

    kind = "comparator_flip"
    FAMILY_NAME = "comparator_flip"

    def generate(
        self,
        case: Case,
        peer_cases: list[Case],
        *,
        seed: int,
        governing_types: list[str],
    ) -> PerturbationBatch:
        warnings: list[str] = []
        perturbations: list[Perturbation] = []

        for gtype in governing_types:
            for target in case.units_of_type(gtype):
                new_content, n = _swap_comparators(target.content)
                if n == 0:
                    warnings.append(
                        f"{case.name}: comparator_flip for {gtype} unit at "
                        f"index {target.index} — no comparators matched"
                    )
                    continue
                new_units = [
                    (
                        Unit(
                            type=u.type,
                            content=new_content,
                            raw_header=u.raw_header,
                            index=u.index,
                        )
                        if u.index == target.index
                        else u
                    )
                    for u in case.units
                ]
                perturbations.append(
                    Perturbation(
                        case_name=case.name,
                        kind="comparator_flip",
                        variant_id=f"comparator_flip-{gtype}-01",
                        rendered_markdown=render_case(case.preamble, new_units),
                        notes={
                            "governing_type": gtype,
                            "position_modified": target.index,
                            "n_comparators_swapped": n,
                        },
                    )
                )
        return PerturbationBatch(perturbations=perturbations, warnings=warnings)


# ─── Sensitivity: polarity flip ───────────────────────────────────────────

_POLARITY_PAIRS: tuple[tuple[str, str], ...] = (
    ("approved", "denied"),
    ("accepted", "rejected"),
    ("committed", "withdrawn"),
    ("validated", "unvalidated"),
    ("signed", "unsigned"),
    ("met", "unmet"),
    ("met", "not met"),
    ("paid", "unpaid"),
    ("profitable", "unprofitable"),
    ("sustainable", "unsustainable"),
    ("granted", "revoked"),
    ("allowed", "prohibited"),
    ("certified", "uncertified"),
)


def _swap_polarity(text: str) -> tuple[str, int]:
    """Returns (new_text, n_swaps). First-match-wins on overlapping entries."""
    swaps = 0
    out = text
    for src, dst in _POLARITY_PAIRS:
        pattern = re.compile(r"\b" + re.escape(src) + r"\b", re.IGNORECASE)
        new_out, n = pattern.subn(dst, out, count=1)
        if n > 0:
            out = new_out
            swaps += n
    return out, swaps


class PolarityFlipGenerator:
    """Swaps closed-list polarity words within governing sections."""

    kind = "polarity_flip"
    FAMILY_NAME = "polarity_flip"

    def generate(
        self,
        case: Case,
        peer_cases: list[Case],
        *,
        seed: int,
        governing_types: list[str],
    ) -> PerturbationBatch:
        warnings: list[str] = []
        perturbations: list[Perturbation] = []

        for gtype in governing_types:
            for target in case.units_of_type(gtype):
                new_content, n = _swap_polarity(target.content)
                if n == 0:
                    warnings.append(
                        f"{case.name}: polarity_flip for {gtype} unit at "
                        f"index {target.index} — no polarity words matched"
                    )
                    continue
                new_units = [
                    (
                        Unit(
                            type=u.type,
                            content=new_content,
                            raw_header=u.raw_header,
                            index=u.index,
                        )
                        if u.index == target.index
                        else u
                    )
                    for u in case.units
                ]
                perturbations.append(
                    Perturbation(
                        case_name=case.name,
                        kind="polarity_flip",
                        variant_id=f"polarity_flip-{gtype}-01",
                        rendered_markdown=render_case(case.preamble, new_units),
                        notes={
                            "governing_type": gtype,
                            "position_modified": target.index,
                            "n_polarity_swapped": n,
                        },
                    )
                )
        return PerturbationBatch(perturbations=perturbations, warnings=warnings)


# ─── Invariance: rhetorical families with structural constraints ─────────
#
# These four families were cut from the original v0.3 Pillar 3 scope for
# requiring labeling-study validation. Reinstated per SBA direction with
# rule-based structural constraints that each docstring describes. The
# constraints reduce but do not eliminate the semantic risk for hedges
# and some discourse markers. A reviewer reading the paper can
# reasonably push back on these families; non_governing_duplication and
# meta_commentary_injection (restricted to non-governing sections)
# carry the lowest risk because they operate on decision-irrelevant
# content by design.


_HEDGES: tuple[str, ...] = ("perhaps", "possibly", "arguably", "ostensibly")


_NEGATION_TOKENS: tuple[str, ...] = (
    "no", "not", "none", "never", "nothing", "cannot", "no-", "non-",
)


# Noun-phrase heads the hedge inserter will target. Matches simple DET + N
# patterns only — doesn't chase complex NPs. Conservative by design.
_NP_HEAD_RE = re.compile(
    r"\b(the|our|its|their|a|an)\s+([A-Za-z][A-Za-z-]{2,})\b",
    re.IGNORECASE,
)


class HedgeInjectionGenerator:
    """Inserts hedges before determiner-headed noun phrases ONLY.

    Structural constraints (by construction):
      - never before a word in the negation token list (protects polarity)
      - never adjacent to a numeric token (protects quantitative claims)
      - never inside a governing section (decision weight stays intact)

    What's protected: polarity, numeric literals, governing content.
    What's NOT protected: epistemic modality. Hedges by definition
    weaken epistemic commitment — that's what the operator does. A
    pipeline sensitive to epistemic strength will still move on hedged
    non-governing prose. Reader interprets this as a diagnostic signal,
    not a false-positive invariance failure: cross-section register
    leakage is a real LLM failure mode.
    """

    kind = "hedge_injection"
    FAMILY_NAME = "hedge_injection"
    TARGET_COUNT = 3

    def generate(
        self,
        case: Case,
        peer_cases: list[Case],
        *,
        seed: int,
        governing_types: list[str],
    ) -> PerturbationBatch:
        non_gov_units = [u for u in case.units if u.type not in governing_types]
        if not non_gov_units:
            return PerturbationBatch(
                perturbations=[],
                warnings=[
                    f"{case.name}: hedge_injection skipped — all sections "
                    f"are governing types"
                ],
            )

        rng = rng_for(seed, "hedge_injection", case.name)
        perturbations: list[Perturbation] = []

        for i in range(self.TARGET_COUNT):
            # Pick a non-governing section with at least one eligible site.
            sites: list[tuple[Unit, re.Match]] = []
            for u in non_gov_units:
                for m in _NP_HEAD_RE.finditer(u.content):
                    # Guard: preceding 15 chars shouldn't contain a negation
                    # token or a number.
                    preceding = u.content[max(0, m.start() - 15):m.start()].lower()
                    if any(tok in preceding.split() for tok in _NEGATION_TOKENS):
                        continue
                    if re.search(r"\d", preceding):
                        continue
                    sites.append((u, m))
            if not sites:
                break
            target_unit, target_match = rng.choice(sites)
            hedge = rng.choice(_HEDGES)
            start = target_match.start()
            new_body = (
                target_unit.content[:start]
                + hedge + " "
                + target_unit.content[start:]
            )
            new_units = [
                (
                    Unit(
                        type=u.type, content=new_body,
                        raw_header=u.raw_header, index=u.index,
                    )
                    if u.index == target_unit.index else u
                )
                for u in case.units
            ]
            perturbations.append(
                Perturbation(
                    case_name=case.name,
                    kind="hedge_injection",
                    variant_id=f"hedge_injection-{i + 1:02d}",
                    rendered_markdown=render_case(case.preamble, new_units),
                    notes={
                        "hedge": hedge,
                        "section_type": target_unit.type,
                        "insertion_offset": start,
                    },
                )
            )
        return PerturbationBatch(perturbations=perturbations)


# Politeness: rewrite imperatives as polite requests via a closed template
# set. On a declarative corpus this has few insertion sites — logged as
# caps for transparency when the family finds nothing to do.

_IMPERATIVE_VERB_START = re.compile(
    r"^(Verify|Inspect|Confirm|Check|Review|Ensure|Validate|Update|Add|Remove)\s+",
    re.MULTILINE,
)


class PolitenessInjectionGenerator:
    """Rewrites imperative-verb-initial sentences with 'Please, …'.

    Closed template: "Please, <lowercased first word> …" applied only
    when the sentence starts with a verb from the imperative closed
    list. Declarative prose (most of the VA corpus) has no insertion
    sites; the family emits a cap and produces zero variants for
    those cases — honest coverage reporting.
    """

    kind = "politeness_injection"
    FAMILY_NAME = "politeness_injection"
    TARGET_COUNT = 2

    def generate(
        self,
        case: Case,
        peer_cases: list[Case],
        *,
        seed: int,
        governing_types: list[str],
    ) -> PerturbationBatch:
        non_gov_units = [u for u in case.units if u.type not in governing_types]
        rng = rng_for(seed, "politeness_injection", case.name)
        perturbations: list[Perturbation] = []

        for i in range(self.TARGET_COUNT):
            # Look for a sentence starting with an imperative verb inside
            # a non-governing section.
            sites: list[tuple[Unit, re.Match]] = []
            for u in non_gov_units:
                for m in _IMPERATIVE_VERB_START.finditer(u.content):
                    sites.append((u, m))
            if not sites:
                caps = [
                    f"{case.name}: politeness_injection capped at 0 — no "
                    f"imperative-verb-initial sentences found in "
                    f"non-governing sections"
                ]
                return PerturbationBatch(perturbations=perturbations, caps=caps)
            target_unit, target_match = rng.choice(sites)
            verb = target_match.group(1)
            replacement = f"Please, {verb.lower()} "
            new_body = (
                target_unit.content[:target_match.start()]
                + replacement
                + target_unit.content[target_match.end():]
            )
            new_units = [
                (
                    Unit(
                        type=u.type, content=new_body,
                        raw_header=u.raw_header, index=u.index,
                    )
                    if u.index == target_unit.index else u
                )
                for u in case.units
            ]
            perturbations.append(
                Perturbation(
                    case_name=case.name,
                    kind="politeness_injection",
                    variant_id=f"politeness_injection-{i + 1:02d}",
                    rendered_markdown=render_case(case.preamble, new_units),
                    notes={
                        "original_verb": verb,
                        "section_type": target_unit.type,
                    },
                )
            )
        return PerturbationBatch(perturbations=perturbations)


# Discourse markers: only additive/non-contrastive ("additionally",
# "furthermore"). Never "however", "therefore", "nonetheless", etc.

_NON_LOGICAL_MARKERS: tuple[str, ...] = ("Additionally", "Furthermore", "Also")


class DiscourseMarkerInjectionGenerator:
    """Inserts only additive (non-logical/non-contrastive) markers at
    sentence boundaries inside non-governing sections.

    Protected: no contrastive or causal relations introduced; the
    marker implies addition, which is typically closer to what the
    adjacent sentences were already doing in listed-evidence prose.
    Not fully protected: "furthermore" weakly implies the next sentence
    strengthens a cumulative argument — LLMs may take that as a cue.
    """

    kind = "discourse_marker_injection"
    FAMILY_NAME = "discourse_marker_injection"
    TARGET_COUNT = 3

    def generate(
        self,
        case: Case,
        peer_cases: list[Case],
        *,
        seed: int,
        governing_types: list[str],
    ) -> PerturbationBatch:
        non_gov_units = [u for u in case.units if u.type not in governing_types]
        rng = rng_for(seed, "discourse_marker_injection", case.name)
        perturbations: list[Perturbation] = []

        for i in range(self.TARGET_COUNT):
            candidates = [u for u in non_gov_units if len(_split_sentences(u.content)) >= 2]
            if not candidates:
                break
            target_unit = rng.choice(candidates)
            sentences = _split_sentences(target_unit.content)
            # Insert the marker before a non-first sentence.
            insert_idx = rng.randrange(1, len(sentences))
            marker = rng.choice(_NON_LOGICAL_MARKERS)
            sentences[insert_idx] = f"{marker}, {sentences[insert_idx][0].lower()}{sentences[insert_idx][1:]}"
            new_body = " ".join(sentences)
            new_units = [
                (
                    Unit(
                        type=u.type, content=new_body,
                        raw_header=u.raw_header, index=u.index,
                    )
                    if u.index == target_unit.index else u
                )
                for u in case.units
            ]
            perturbations.append(
                Perturbation(
                    case_name=case.name,
                    kind="discourse_marker_injection",
                    variant_id=f"discourse_marker_injection-{i + 1:02d}",
                    rendered_markdown=render_case(case.preamble, new_units),
                    notes={
                        "marker": marker,
                        "section_type": target_unit.type,
                        "sentence_index": insert_idx,
                    },
                )
            )
        return PerturbationBatch(perturbations=perturbations)


# Meta-commentary: insert framing phrases only in non-governing sections.

_META_FRAMES: tuple[str, ...] = (
    "As a factual summary, ",
    "To restate the context, ",
    "For the record, ",
)


class MetaCommentaryInjectionGenerator:
    """Inserts a framing statement at the start of a non-governing section.

    Protected: governing sections are untouched — decision-relevant
    content never gets a meta-commentary frame. The frame is a
    restatement-like cue; LLMs may interpret the frame as heightening
    attention to the framed content, but since that content is
    non-governing by construction, the decision axis is protected by
    the target selection.
    """

    kind = "meta_commentary_injection"
    FAMILY_NAME = "meta_commentary_injection"
    TARGET_COUNT = 2

    def generate(
        self,
        case: Case,
        peer_cases: list[Case],
        *,
        seed: int,
        governing_types: list[str],
    ) -> PerturbationBatch:
        non_gov_units = [u for u in case.units if u.type not in governing_types]
        if not non_gov_units:
            return PerturbationBatch(
                perturbations=[],
                warnings=[
                    f"{case.name}: meta_commentary_injection skipped — all "
                    f"sections are governing types"
                ],
            )
        rng = rng_for(seed, "meta_commentary_injection", case.name)
        perturbations: list[Perturbation] = []

        for i in range(self.TARGET_COUNT):
            target_unit = rng.choice(non_gov_units)
            frame = rng.choice(_META_FRAMES)
            # Lowercase the first letter of the existing body if it starts
            # with a capitalized word, to chain grammatically.
            body = target_unit.content.lstrip()
            if body and body[0].isupper():
                body = body[0].lower() + body[1:]
            new_body = frame + body
            new_units = [
                (
                    Unit(
                        type=u.type, content=new_body,
                        raw_header=u.raw_header, index=u.index,
                    )
                    if u.index == target_unit.index else u
                )
                for u in case.units
            ]
            perturbations.append(
                Perturbation(
                    case_name=case.name,
                    kind="meta_commentary_injection",
                    variant_id=f"meta_commentary_injection-{i + 1:02d}",
                    rendered_markdown=render_case(case.preamble, new_units),
                    notes={
                        "frame": frame.strip(),
                        "section_type": target_unit.type,
                    },
                )
            )
        return PerturbationBatch(perturbations=perturbations)


# ─── Registry ─────────────────────────────────────────────────────────────


PILLAR3_FAMILIES: dict[str, type] = {
    # Invariance (presentation-layer)
    "whitespace_jitter": WhitespaceJitterGenerator,
    "punctuation_normalize": PunctuationNormalizeGenerator,
    "bullet_reformat": BulletReformatGenerator,
    "non_governing_duplication": NonGoverningDuplicationGenerator,
    # Invariance (rhetorical, rule-based with structural constraints)
    "hedge_injection": HedgeInjectionGenerator,
    "politeness_injection": PolitenessInjectionGenerator,
    "discourse_marker_injection": DiscourseMarkerInjectionGenerator,
    "meta_commentary_injection": MetaCommentaryInjectionGenerator,
    # Sensitivity (mechanical)
    "numeric_magnitude": NumericMagnitudeGenerator,
    "comparator_flip": ComparatorFlipGenerator,
    "polarity_flip": PolarityFlipGenerator,
}
