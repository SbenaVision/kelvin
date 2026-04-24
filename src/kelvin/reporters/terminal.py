"""Terminal reporter for kelvin check.

Renders a 58-column summary box to stdout after a run completes.
Handles ANSI colour (auto-detected via TTY), plain/no-colour mode,
degenerate run states, and partial-failure footnotes — exactly per spec.

Public API
----------
    render(run_scores, elapsed_s=..., decision_field=..., no_color=False, out=None)
"""

from __future__ import annotations

import os
import re
import sys
from typing import TextIO

from kelvin.types import CaseScores, RunScores

# ── Box geometry ─────────────────────────────────────────────────────────────

_BOX_WIDTH   = 58   # total visual width including border chars
_INNER_WIDTH = 56   # _BOX_WIDTH - 2
_INDENT      = "   "  # 3-space left margin for all content lines

# ── ANSI codes ────────────────────────────────────────────────────────────────

_BLUE  = "\033[34m"   # cool blue  — invariance bar filled cells
_AMBER = "\033[33m"   # warm amber — sensitivity bar filled cells
_DIM   = "\033[2m"    # dimmed     — footnotes
_RESET = "\033[0m"

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def _vlen(s: str) -> int:
    """Visual length of a string: strip ANSI codes before measuring."""
    return len(_ANSI_RE.sub("", s))


# ── Box primitives ────────────────────────────────────────────────────────────

def _top() -> str:
    title  = "─ Kelvin Report "                       # 16 chars
    dashes = "─" * (_BOX_WIDTH - 2 - len(title))      # 40 dashes
    return f"┌{title}{dashes}┐"


def _bottom() -> str:
    return "└" + "─" * _INNER_WIDTH + "┘"


def _empty() -> str:
    return "│" + " " * _INNER_WIDTH + "│"


def _row(content: str) -> str:
    """Pad *content* to _INNER_WIDTH visual columns and wrap in box borders."""
    pad = max(0, _INNER_WIDTH - _vlen(content))
    return f"│{content}{' ' * pad}│"


# ── Verdict phrases ───────────────────────────────────────────────────────────

def _verdict(score: float, kind: str) -> str:
    if kind == "invariance":
        if score >= 0.90: return "rock-steady — good"
        if score >= 0.70: return "mostly — good"
        if score >= 0.50: return "uneven — watch"
        if score >= 0.30: return "drifting — concerning"
        return "unstable — concerning"
    # sensitivity
    if score >= 0.90: return "sharply reactive — good"
    if score >= 0.70: return "reactive — good"
    if score >= 0.50: return "partial — watch"
    if score >= 0.30: return "sluggish — concerning"
    return "barely — concerning"


# ── Progress bar ──────────────────────────────────────────────────────────────

def _bar(score: float, colour: str, plain: bool) -> str:
    """Ten-cell bar. ANSI-coloured in colour mode; bracketed ASCII in plain."""
    filled = round(score * 10)
    empty  = 10 - filled
    if plain:
        return "[" + "#" * filled + "-" * empty + "]"
    return f"{colour}{'█' * filled}{_RESET}{'░' * empty}"


# ── Elapsed formatting ────────────────────────────────────────────────────────

def _fmt_elapsed(seconds: float) -> str:
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    return f"{s // 60}m {s % 60:02d}s"


# ── Perturbation counts ───────────────────────────────────────────────────────

def _all_sp(case: CaseScores) -> list:
    return [
        *case.reorder,
        *case.pad_length,
        *case.pad_content,
        *(sp for sps in case.swaps_by_type.values() for sp in sps),
    ]


def _count_perts(cases: list[CaseScores]) -> tuple[int, int]:
    """Return (total, failed) perturbation counts across all cases."""
    total = failed = 0
    for c in cases:
        sps    = _all_sp(c)
        total  += len(sps)
        failed += sum(1 for sp in sps if not sp.invocation.ok)
    return total, failed


def _fully_skipped_cases(cases: list[CaseScores]) -> list[str]:
    """Cases whose baseline passed but every perturbation invocation failed."""
    out = []
    for c in cases:
        if not c.baseline_ok:
            continue
        sps = _all_sp(c)
        if sps and all(not sp.invocation.ok for sp in sps):
            out.append(c.case_name)
    return out


# ── Diagnostic line ───────────────────────────────────────────────────────────

def _diagnostic_rows(
    run_scores: RunScores,
    decision_field: str,
) -> list[str]:
    """Return indented content strings (no borders) for the diagnostic block.

    Exactly one diagnostic finding — never more.
    """
    sens = run_scores.sensitivity
    inv  = run_scores.invariance
    has_governing = bool(run_scores.governing_types)
    n_cases = len(run_scores.cases)

    # Rule 1 — governing type is being ignored
    if has_governing and n_cases > 1 and sens is not None and sens < 0.30:
        for gtype, (mean, sample) in run_scores.sensitivity_by_type.items():
            if mean is None or sample == 0:
                continue
            if mean < 0.50:
                no_change = sum(
                    1
                    for c in run_scores.cases
                    for sp in c.swaps_by_type.get(gtype, [])
                    if sp.distance is not None and sp.distance == 0.0
                )
                type_disp = gtype.replace("_", " ")
                return [
                    f"{_INDENT}⚠  {type_disp.capitalize()}s are being ignored.",
                    f"{_INDENT}   Swapping the governing {gtype} for a",
                    f"{_INDENT}   different valid one didn't change the",
                    f"{_INDENT}   {decision_field} in {no_change} of {sample} cases.",
                ]

    # Rule 2 — invariance drifts
    if inv is not None and inv < 0.50:
        buckets = [
            ("reorder",     "presentation",  [sp for c in run_scores.cases for sp in c.reorder]),
            ("pad_length",  "input length",  [sp for c in run_scores.cases for sp in c.pad_length]),
            ("pad_content", "distractors",   [sp for c in run_scores.cases for sp in c.pad_content]),
        ]
        rates: list[tuple[str, str, int, int]] = []
        for kind_word, change_word, sps in buckets:
            scored = sum(1 for sp in sps if sp.distance is not None)
            changed = sum(
                1 for sp in sps
                if sp.distance is not None and sp.distance > 0
            )
            rates.append((kind_word, change_word, changed, scored))

        ranked = sorted(
            [r for r in rates if r[3] > 0],
            key=lambda r: (r[2] / r[3] if r[3] else 0.0),
            reverse=True,
        )
        if ranked:
            kind_word, change_word, n, m = ranked[0]
            return [
                f"{_INDENT}\u26a0  Output drifts on {kind_word}. The {decision_field}",
                f"{_INDENT}   changed in {n} of {m} cases when only",
                f"{_INDENT}   {change_word} changed.",
            ]

    # Rule 3 — both healthy; check for hidden per-case variance
    if inv is not None:
        per_case_inv = []
        for c in run_scores.cases:
            ds = c.invariance_distances
            if ds:
                per_case_inv.append(1.0 - sum(ds) / len(ds))
        if len(per_case_inv) >= 2:
            mean_val = sum(per_case_inv) / len(per_case_inv)
            variance = sum((x - mean_val) ** 2 for x in per_case_inv) / len(per_case_inv)
            if variance > 0.09:   # std dev > 0.30
                return [
                    f"{_INDENT}Aggregate looks healthy but per-case variance",
                    f"{_INDENT}is large. Open kelvin/report.html and sort",
                    f"{_INDENT}by worst_case.",
                ]

    return [
        f"{_INDENT}Both signals look healthy. Spot-check",
        f"{_INDENT}kelvin/report.html for per-case anomalies.",
    ]


# ── Main builder ──────────────────────────────────────────────────────────────

def _build(
    run_scores: RunScores,
    *,
    elapsed_s: float,
    decision_field: str,
    plain: bool,
) -> list[str]:
    rows: list[str] = []

    total_perts, failed_perts = _count_perts(run_scores.cases)
    skipped                   = _fully_skipped_cases(run_scores.cases)
    n_ok_cases                = len([c for c in run_scores.cases if c.baseline_ok])
    has_governing             = bool(run_scores.governing_types)
    n_all_cases               = len(run_scores.cases)

    inv  = run_scores.invariance
    sens = run_scores.sensitivity

    # ── Top ──────────────────────────────────────────────────────────────────
    rows.append(_top())
    rows.append(_empty())

    # ── Single-case banner (escalated in Tier 2) ─────────────────────────────
    if run_scores.single_case_run:
        rows.append(_row(
            f"{_INDENT}\u26a0  Single-case run — pad_content and swap"
        ))
        rows.append(_row(f"{_INDENT}   skipped. Add peer cases for full signal."))
        rows.append(_empty())

    # ── Run line ──────────────────────────────────────────────────────────────
    rows.append(_row(
        f"{_INDENT}{n_ok_cases} cases · {total_perts} perturbations"
        f" · {_fmt_elapsed(elapsed_s)}"
    ))
    rows.append(_empty())

    # ── Invariance block ──────────────────────────────────────────────────────
    if inv is not None:
        rows.append(_row(f"{_INDENT}{'Invariance':<14}{inv:.2f}"))
        rows.append(_row(f"{_INDENT}Does your pipeline stay calm when nothing"))
        rows.append(_row(f"{_INDENT}important changes?"))
        rows.append(_row(
            f"{_INDENT}{_bar(inv, _BLUE, plain)}   {_verdict(inv, 'invariance')}"
        ))
        rows.append(_empty())

    # ── Sensitivity block (or replacement text) ───────────────────────────────
    if not has_governing:
        rows.append(_row(f"{_INDENT}Sensitivity not measured — no governing"))
        rows.append(_row(f"{_INDENT}types declared in kelvin.yaml."))
        rows.append(_empty())
    elif n_all_cases == 1:
        rows.append(_row(f"{_INDENT}Sensitivity not measured — only one case"))
        rows.append(_row(f"{_INDENT}in run, no peers for governing units."))
        rows.append(_empty())
    elif sens is not None:
        rows.append(_row(f"{_INDENT}{'Sensitivity':<14}{sens:.2f}"))
        rows.append(_row(f"{_INDENT}Does your pipeline react when something"))
        rows.append(_row(f"{_INDENT}important changes?"))
        rows.append(_row(
            f"{_INDENT}{_bar(sens, _AMBER, plain)}   {_verdict(sens, 'sensitivity')}"
        ))
        rows.append(_empty())

    # ── Kelvin score block ────────────────────────────────────────────────────
    if run_scores.kelvin_score is not None:
        rows.append(_row(
            f"{_INDENT}{'Kelvin score':<14}{run_scores.kelvin_score:.2f}"
        ))
        rows.append(_row(f"{_INDENT}K = (1 - Inv) + (1 - Sens).  Range [0, 2],"))
        rows.append(_row(f"{_INDENT}lower = more anchored."))
        rows.append(_empty())

    # ── Pillar 1: noise floor + calibrated K (opt-in) ─────────────────────────
    if run_scores.noise_floor_eta is not None:
        # Replay count is per-case; pull it from the first case with data.
        replay_n = next(
            (len(c.baseline_replays) for c in run_scores.cases if c.baseline_replays),
            0,
        )
        rows.append(_row(
            f"{_INDENT}{'Noise floor η':<14}{run_scores.noise_floor_eta:.3f}"
        ))
        rows.append(_row(
            f"{_INDENT}Measured across {replay_n} replays per case."
        ))
        rows.append(_empty())
        if run_scores.kelvin_score_calibrated is not None:
            rows.append(_row(
                f"{_INDENT}{'K_cal':<14}{run_scores.kelvin_score_calibrated:.2f}"
            ))
            rows.append(_row(
                f"{_INDENT}K after calibrating for stochasticity."
            ))
        else:
            rows.append(_row(
                f"{_INDENT}{'K_cal':<14}—"
            ))
            rows.append(_row(
                f"{_INDENT}Noise exceeds invariance signal; unmeasurable."
            ))
        rows.append(_empty())

    # ── Diagnostic ────────────────────────────────────────────────────────────
    for line in _diagnostic_rows(run_scores, decision_field):
        rows.append(_row(line))
    rows.append(_empty())

    # ── Honest framing + pointer ──────────────────────────────────────────────
    rows.append(_row(f"{_INDENT}Diagnostic signals — not truth metrics."))
    rows.append(_row(f"{_INDENT}\u2192 kelvin/report.html for per-case drill-down"))

    # ── Footnotes ─────────────────────────────────────────────────────────────
    if failed_perts > 0:
        note = (
            f"{_INDENT}{failed_perts} of {total_perts} perturbations"
            f" failed (logged in kelvin/)."
        )
        if not plain:
            note = (
                f"{_INDENT}{_DIM}{failed_perts} of {total_perts} perturbations"
                f" failed (logged in kelvin/).{_RESET}"
            )
        rows.append(_row(note))

    for case_name in skipped:
        rows.append(_row(
            f"{_INDENT}{case_name} skipped — pipeline returned non-zero"
            f" on every perturbation."
        ))

    rows.append(_empty())
    rows.append(_bottom())

    return rows


# ── Public entry point ────────────────────────────────────────────────────────

def render(
    run_scores: RunScores,
    *,
    elapsed_s: float,
    decision_field: str,
    no_color: bool = False,
    out: TextIO | None = None,
) -> None:
    """Print the 58-column terminal summary box to *out* (default: stdout)."""
    if out is None:
        out = sys.stdout

    plain = (
        no_color
        or bool(os.environ.get("NO_COLOR"))
        or not getattr(out, "isatty", lambda: False)()
    )

    for line in _build(
        run_scores,
        elapsed_s=elapsed_s,
        decision_field=decision_field,
        plain=plain,
    ):
        print(line, file=out)
