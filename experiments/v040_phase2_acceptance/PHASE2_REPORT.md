# Phase 2 deliverable — Findings + Reporters + CLI

**Date:** 2026-04-25
**Worktree:** `.claude/worktrees/v040-phase1`
**Status:** PASS (all acceptance criteria met).

## Summary

Phase 2 ships the practitioner-facing v0.4 surface on top of the
Phase 1 maturity score:

- **Findings + recommendations** (`kelvin/findings.py`,
  `kelvin/recommendations.py`) — hand-curated rule tables that turn
  the per-axis sub-scores into plain-language statements and
  concrete fixes. No AI, no learning, no soft logic.
- **Variance / impact decomposition** (`kelvin/variance.py`) —
  default ranks axes by drag on the maturity score; verbose mode
  surfaces a per-family contribution breakdown.
- **Three reporters** (`kelvin/reporters/{practitioner,markdown,json_reporter}.py`):
  - `practitioner` (default): one-screen, < 30-line, no jargon,
    silent-pillar aware, numeric hidden by default.
  - `json_reporter`: versioned structured output with
    `schema_version: "1.0"` for downstream tooling.
  - `markdown`: PR-friendly, same content, MD format.
- **CLI flags** (`kelvin/cli.py`): `--verbose`, `--research`,
  `--report-format {practitioner,json,markdown}`, `--version`.
- **Silent-pillar handling** (per `docs/PHASE_2_SCOPE.md`): verdict
  becomes "Partially measured" when any standard pillar is silent;
  numeric is banner-flagged in `--verbose`; "Top fix" promotes the
  make-it-measurable action.

## Acceptance criteria

| AC | Description                                                     | Result |
| -- | ----------------------------------------------------------------| ------ |
| AC1 | Naive user understands the output (manual review)              | **PASS** — sample outputs in `outputs/*_default.txt` |
| AC2 | Default practitioner output < 30 lines                         | **PASS** — 12–22 lines across 6 scenarios |
| AC3 | No statistical jargon ("ANOVA", "F-stat", "p-value", ...)      | **PASS** — regex-grep on default + verbose + markdown |
| AC4 | Recommendations are concrete actions in <1 hour                | **PASS** — hand-curated table in `recommendations.py` |
| AC5 | Anchor verdict ordering: constant ≤ brittle ≤ mid ≤ one_mod ≤ grounded (categorical) | **PASS** — see ranks below |
| AC6 | `--research` preserves v0.3.0 byte-compat output               | **PASS** — `render_v03_terminal=True` path retained |
| AC7 | Envelop produces "Partially measured", NOT "Production-ready"  | **PASS** — Pillar 2 silent → category overridden |

### AC2 — line counts per scenario

```
constant            18 lines  (Not production-ready)
brittle             18 lines  (Not production-ready)
mid_issue           22 lines  (Needs work)
one_moderate_issue  18 lines  (Needs work)
grounded_oracle     12 lines  (Production-ready)
envelop             18 lines  (Partially measured)
```

### AC5 — anchor ordering

Categorical ranks (Not production-ready=0, Needs work=1,
Production-ready=2):

```
constant            0
brittle             0
mid_issue           1
one_moderate_issue  1
grounded_oracle     2
```

Monotone non-decreasing across the spec-defined order. Numeric
1–10 is corpus-coupled and only enforced under `--verbose` (per
the Phase 1 calibration finding); the categorical surface is the
production contract.

### AC7 — Envelop silent-Pillar-2 containment

```
category:        Partially measured
pillar_coverage: {"pillar_1": True, "pillar_2": False, "pillar_3": True}
silent_pillars:  {"pillar_2": "swap_condition_format_mismatch"}
```

The default reporter surfaces this state with explicit per-pillar
rows and promotes a make-it-measurable Top fix
("Restructure gate_rule bodies …, or wait for v0.5's broader
format coverage."). Numeric is hidden by default; under `--verbose`
it carries the banner "⚠ partial coverage — not comparable to
fully-measured runs."

## Test counts

```
tests/test_findings.py            21 tests
tests/test_recommendations.py     10 tests
tests/test_variance.py             7 tests
tests/test_reporter_practitioner.py 18 tests
tests/test_reporter_json.py       11 tests
tests/test_reporter_markdown.py    8 tests
tests/test_cli.py                  6 tests
                                  ----
                            new   81 tests
                       full suite 457 passing
```

All Phase 1 tests still pass; no regressions.

## Files added in Phase 2

```
src/kelvin/findings.py
src/kelvin/recommendations.py
src/kelvin/variance.py
src/kelvin/reporters/practitioner.py
src/kelvin/reporters/json_reporter.py
(markdown.py rewritten in place)

tests/test_findings.py
tests/test_recommendations.py
tests/test_variance.py
tests/test_reporter_practitioner.py
tests/test_reporter_json.py
tests/test_reporter_markdown.py
tests/test_cli.py

experiments/v040_phase2_acceptance/run_acceptance.py
experiments/v040_phase2_acceptance/PHASE2_REPORT.md  (this file)
experiments/v040_phase2_acceptance/outputs/*           (sample renders)
```

## Files modified in Phase 2

```
src/kelvin/__init__.py        (version bump → 0.4.0)
src/kelvin/score.py           (pillar_coverage + silent-pillar override)
src/kelvin/cli.py             (--verbose, --research, --report-format, --version)
src/kelvin/check.py           (render_v03_terminal opt-out for v0.4 reporter)
tests/test_score.py           (5 silent-pillar tests + helper update)
```

## Known limitations / v0.5 backlog

- Numeric 1–10 score remains **corpus-coupled** — surfaced only
  in `--verbose` and never as the headline. The categorical
  verdict is the production contract.
- Envelop-style format mismatches (Pillar 2 silently failing on
  non-canonical gate_rule bodies) are correctly *contained* by
  the "Partially measured" state, but the underlying coverage
  fix is the v0.5 backlog item B-3 (`swap_condition` format
  generalization).
- Family-level brittleness can be invisible in the headline
  number when only a single family fails (B-1 / MIN-per-family
  aggregation, deferred to v0.5).

## Stopping condition

Phase 2 is complete and locked. Phase 3 (init wizard, polish,
release) is **NOT** started in this work and should be picked up
in a subsequent session, per the spec.
