"""Pad-length perturbation.

Insert 2-4 neutral filler sections (drawn from a fixed bank of generic
administrative prose) into the current case at random positions. 3 variants
per case. Runs regardless of peer-case availability — works in single-case
runs where `pad_content` and `swap` cannot.

Probes *presentation-length robustness*: does the decision drift when the
input grows in length without introducing any new decision-relevant
content? Paired with `PadContentGenerator`, which probes distractor-content
robustness.

Filler sections are inserted as `## Reference Note` blocks. The bank is
curated to avoid language that pattern-matches common governing-unit types
(gate rules, screening rules, approval criteria, etc.) — each paragraph
reads as routine administrative metadata. If a user happens to declare
`reference_note` as a unit type, Kelvin's type-discovery echo will surface
the collision at run start.
"""

from __future__ import annotations

from kelvin.parser import render_case
from kelvin.perturbations import rng_for
from kelvin.types import Case, Perturbation, PerturbationBatch, Unit

TARGET_COUNT = 3
MIN_INSERT = 2
MAX_INSERT = 4

FILLER_HEADER_RAW = "Reference Note"

# A curated bank of neutral administrative paragraphs — varied in length,
# none of which pattern-match decision criteria. Picked with replacement,
# so the bank does not need to be large.
_FILLER_POOL: tuple[str, ...] = (
    "This document is reviewed quarterly by the operations team. Any "
    "revisions are tracked in the internal revision log maintained "
    "alongside the records archive.",

    "Records in this section are retained for seven years in accordance "
    "with the organization's standard document-retention policy. Requests "
    "for earlier access should be routed through the records coordinator "
    "before being escalated.",

    "Formatting in the following sections follows the internal style "
    "guide last updated in the previous fiscal year. Headings use title "
    "case, paragraphs are single-spaced, and footnotes appear inline "
    "rather than at the bottom of the page.",

    "Contact details for document owners are maintained in a separate "
    "directory and are intentionally omitted from this file to reduce "
    "the need for revisions when personnel changes occur. The directory "
    "is refreshed on a rolling basis throughout the year.",

    "Translations of this document, where available, are produced by an "
    "external vendor and are provided for convenience only. In the event "
    "of any inconsistency between the source text and a translated "
    "version, the source text takes precedence for all operational "
    "purposes.",

    "Printed copies of this document are considered uncontrolled. The "
    "canonical version is the one stored in the shared repository; "
    "users consulting a printout should verify freshness against the "
    "timestamp shown in the repository metadata before acting on any "
    "of the content below.",

    "Questions about the scope or applicability of any section should "
    "be directed to the administrative coordinator assigned to the "
    "relevant workstream. Routine clarifications are typically resolved "
    "within one business day.",

    "Accessibility accommodations for reviewers are available upon "
    "request. The standard accommodations list is maintained separately "
    "and covers alternate-format documents, extended review windows, "
    "and live walkthroughs with a subject-matter liaison where needed.",
)


class PadLengthGenerator:
    kind = "pad_length"

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

        rng = rng_for(seed, "pad_length", case.name)
        perturbations: list[Perturbation] = []

        for i in range(TARGET_COUNT):
            insert_count = rng.randint(MIN_INSERT, MAX_INSERT)
            picks = [rng.choice(_FILLER_POOL) for _ in range(insert_count)]

            new_units = list(case.units)
            inserted_notes: list[dict] = []
            for paragraph in picks:
                pos = rng.randint(0, len(new_units))
                filler_unit = Unit(
                    type="reference_note",
                    content=paragraph,
                    raw_header=FILLER_HEADER_RAW,
                    index=-1,   # sentinel: filler, not from the source case
                )
                new_units.insert(pos, filler_unit)
                inserted_notes.append(
                    {
                        "position": pos,
                        "length_chars": len(paragraph),
                    }
                )

            variant_id = f"pad_length-{i + 1:02d}"
            perturbations.append(
                Perturbation(
                    case_name=case.name,
                    kind="pad_length",
                    variant_id=variant_id,
                    rendered_markdown=render_case(case.preamble, new_units),
                    notes={
                        "insert_count": insert_count,
                        "inserted": inserted_notes,
                        "total_chars": sum(len(p) for p in picks),
                    },
                )
            )

        return PerturbationBatch(perturbations=perturbations, warnings=warnings, caps=caps)
