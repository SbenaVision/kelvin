"""Pillar 2 — counterfactual-controlled swap on governing rules.

Where `swap` (v0.2) replaces an entire governing unit (mixing rule-change
and factual-content-change in a single perturbation), `swap_condition`
edits only the *condition clause* of a governing rule while preserving
the focal case's state assertion and justification text. The paired
measurement decomposes raw swap sensitivity:

    Sens(swap_content)   = Rule_Effect + Content_Effect + ε
    Sens(swap_condition) ≈ Rule_Effect

Content_Effect is recovered by subtraction. See `docs/whitepaper.md`
§5.4 for the decomposition theorem and its empirical demonstration.

### Parser contract

Handles gate-rule prose with the shape:
    "[Advance (from X )?to Y] requires: <condition_list>.
     <state_phrase>. <details>"

Where `<state_phrase>` is a sentence indicating coverage of the
requirements — typically one of:
  - "All conditions are met."
  - "None of these conditions are currently met."
  - "Some conditions are met."

Units that do not parse cleanly are skipped with a `caps` entry so the
run report surfaces the clean-parse rate. The ≥80% clean-parse gate
(FALLBACKS.md, paper §5.4) is evaluated at aggregation time.

### Swap contract

For each focal unit that parses cleanly, peers are selected where:
  1. The peer also parses cleanly;
  2. The peer's `<state_phrase>` matches the focal's (textual identity),
     so post-swap coherence is preserved;
  3. The peer's `<condition_list>` differs from the focal's — otherwise
     the swap would be a no-op.

If no eligible peer exists, the case records a warning and generates
zero swap_condition variants.
"""

from __future__ import annotations

import re

from kelvin.parser import render_case
from kelvin.perturbations import rng_for
from kelvin.types import Case, Perturbation, PerturbationBatch, Unit

TARGET_COUNT = 3

# Canonicalized state phrases — exact substring match governs swap eligibility.
# Adding a new phrase here silently widens coverage; no config knob.
_STATE_PHRASES: tuple[str, ...] = (
    "All conditions are met.",
    "None of these conditions are currently met.",
    "Some conditions are met.",
    "All conditions are currently met.",
)

# Gate-rule body must match this pattern. Three capture groups:
#   1. the "requires: " introduction up to and including the colon and space
#   2. the condition list (one or more items, possibly comma-separated)
#   3. the trailing text (state phrase + details)
_GATE_RULE_RE = re.compile(
    r"^(.*?\brequires:\s+)(.+?)\.\s+(.+)$",
    re.DOTALL,
)


class ParsedGateRule:
    """Structured view of a gate-rule unit body."""

    __slots__ = ("intro", "condition_list", "state_phrase", "details")

    def __init__(
        self,
        *,
        intro: str,
        condition_list: str,
        state_phrase: str,
        details: str,
    ) -> None:
        self.intro = intro
        self.condition_list = condition_list
        self.state_phrase = state_phrase
        self.details = details

    def render(self, *, condition_list: str | None = None) -> str:
        """Rebuild the gate-rule body, optionally substituting the condition list."""
        cl = condition_list if condition_list is not None else self.condition_list
        return f"{self.intro}{cl}. {self.state_phrase} {self.details}"


def parse_gate_rule(body: str) -> ParsedGateRule | None:
    """Parse a gate-rule unit body. Returns None on any structural mismatch."""
    m = _GATE_RULE_RE.match(body.strip())
    if not m:
        return None
    intro, condition_list, trailing = m.group(1), m.group(2), m.group(3)
    # Find which known state phrase is at the start of the trailing text.
    state_phrase = None
    details = None
    for phrase in _STATE_PHRASES:
        if trailing.startswith(phrase):
            state_phrase = phrase
            details = trailing[len(phrase):].lstrip()
            break
    if state_phrase is None:
        return None
    return ParsedGateRule(
        intro=intro,
        condition_list=condition_list.strip(),
        state_phrase=state_phrase,
        details=details.strip(),
    )


class SwapConditionGenerator:
    """Counterfactual-controlled swap on governing rules."""

    kind = "swap_condition"

    def generate(
        self,
        case: Case,
        peer_cases: list[Case],
        *,
        seed: int,
        governing_types: list[str],
    ) -> PerturbationBatch:
        warnings: list[str] = []
        caps: list[str] = []
        perturbations: list[Perturbation] = []

        for gtype in governing_types:
            focal_units = case.units_of_type(gtype)
            if not focal_units:
                warnings.append(
                    f"{case.name}: swap_condition skipped for type '{gtype}' — "
                    f"case has no units of this type"
                )
                continue

            # For each focal unit, find peer units with parseable gate-rule
            # structure + matching state phrase + different condition list.
            rng = rng_for(seed, "swap_condition", case.name, gtype)

            for focal_unit in focal_units:
                parsed_focal = parse_gate_rule(focal_unit.content)
                if parsed_focal is None:
                    caps.append(
                        f"{case.name}: swap_condition clean-parse FAILED for "
                        f"{gtype} unit at index {focal_unit.index} "
                        f"(no 'requires:' + state-phrase structure)"
                    )
                    continue

                # Collect eligible peers: same gtype, parse cleanly, matching
                # state phrase, different condition list.
                peer_pool: list[tuple[str, Unit, ParsedGateRule]] = []
                for peer_case in peer_cases:
                    if peer_case.name == case.name:
                        continue
                    for peer_unit in peer_case.units_of_type(gtype):
                        parsed_peer = parse_gate_rule(peer_unit.content)
                        if parsed_peer is None:
                            continue
                        if parsed_peer.state_phrase != parsed_focal.state_phrase:
                            continue
                        if parsed_peer.condition_list == parsed_focal.condition_list:
                            continue
                        peer_pool.append((peer_case.name, peer_unit, parsed_peer))

                if not peer_pool:
                    warnings.append(
                        f"{case.name}: swap_condition found no eligible peers "
                        f"for {gtype} (same state_phrase + different condition list)"
                    )
                    continue

                effective = min(TARGET_COUNT, len(peer_pool))
                if effective < TARGET_COUNT:
                    caps.append(
                        f"{case.name}: swap_condition-{gtype} capped at "
                        f"{effective} (eligible peers={len(peer_pool)}, "
                        f"target={TARGET_COUNT})"
                    )

                picks = rng.sample(peer_pool, effective)

                for i, (peer_name, _peer_unit, parsed_peer) in enumerate(picks):
                    # Rebuild the focal case's units with the governing unit's
                    # condition list replaced.
                    new_content = parsed_focal.render(
                        condition_list=parsed_peer.condition_list
                    )
                    new_units: list[Unit] = []
                    for u in case.units:
                        if u.index == focal_unit.index:
                            new_units.append(
                                Unit(
                                    type=u.type,
                                    content=new_content,
                                    raw_header=u.raw_header,
                                    index=u.index,
                                )
                            )
                        else:
                            new_units.append(u)

                    variant_id = f"swap_condition-{gtype}-{i + 1:02d}"
                    perturbations.append(
                        Perturbation(
                            case_name=case.name,
                            kind="swap_condition",
                            variant_id=variant_id,
                            rendered_markdown=render_case(case.preamble, new_units),
                            notes={
                                "governing_type": gtype,
                                "position_replaced": focal_unit.index,
                                "from_case": peer_name,
                                "state_phrase_preserved": parsed_focal.state_phrase,
                                "focal_condition_list": parsed_focal.condition_list,
                                "peer_condition_list": parsed_peer.condition_list,
                            },
                        )
                    )

        return PerturbationBatch(
            perturbations=perturbations, warnings=warnings, caps=caps
        )
