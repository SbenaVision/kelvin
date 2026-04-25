"""Tests for kelvin.reference_pipelines — anchor pipeline behavior.

Each anchor must:
1. Run end-to-end as a subprocess with --input/--output.
2. Produce valid JSON with `stage_assessment`.
3. Exhibit the behavioral signature it was designed for.

These tests do NOT run the full kelvin check pipeline (that's the
calibration-loop deliverable). They verify the anchor pipelines'
direct shell-command behavior on representative case content.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from kelvin.reference_pipelines import ANCHOR_NAMES, ANCHOR_TARGETS


# Representative case fixtures — minimal markdown that the rule-tracking
# anchors can route. Stored inline (not in cases/) so these tests don't
# depend on the full corpus.

_CASE_GROWTH = """## Venture Description
Real product, real revenue.

## Traction Signal
1,200 paying subscribers; annual revenue run-rate $850K.

## Gate Rule
Advance from Validate to Build requires: founder committed capital,
evidence of demand, and first ventures actively using the platform.
All conditions are met.
"""

_CASE_SCALE = """## Gate Rule
Advance to scale requires durable revenue. All conditions are met.
Annual revenue run-rate $5M.
"""

_CASE_IDEA = """## Gate Rule
None of these conditions are currently met.
"""


# =====================================================================
# Helpers
# =====================================================================


@pytest.fixture
def tmp_io(tmp_path: Path):
    """Provide (input_path, output_path) factories.

    Each call returns a UNIQUE pair of paths so multiple invocations
    inside a single test don't clobber each other.
    """
    counter = {"n": 0}

    def make(text: str) -> tuple[Path, Path]:
        counter["n"] += 1
        i = counter["n"]
        inp = tmp_path / f"case_{i}.md"
        out = tmp_path / f"out_{i}.json"
        inp.write_text(text, encoding="utf-8")
        if out.exists():
            out.unlink()
        return inp, out
    return make


def _run_anchor(name: str, inp: Path, out: Path) -> dict:
    """Invoke the anchor pipeline as a subprocess and return parsed JSON."""
    proc = subprocess.run(
        [sys.executable, "-m", f"kelvin.reference_pipelines.{name}",
         "--input", str(inp), "--output", str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, (
        f"{name} exited with {proc.returncode}: {proc.stderr}"
    )
    assert out.exists(), f"{name} did not produce {out}"
    return json.loads(out.read_text(encoding="utf-8"))


# =====================================================================
# Anchor registry sanity
# =====================================================================

def test_anchor_registry_has_five_entries():
    assert len(ANCHOR_NAMES) == 5
    assert set(ANCHOR_NAMES) == set(ANCHOR_TARGETS.keys())


def test_anchor_targets_match_spec():
    """Spec: 1, 2, 4, 7, 10."""
    assert ANCHOR_TARGETS["constant"]           == 1
    assert ANCHOR_TARGETS["brittle"]            == 2
    assert ANCHOR_TARGETS["mid_issue"]          == 4
    assert ANCHOR_TARGETS["one_moderate_issue"] == 7
    assert ANCHOR_TARGETS["grounded_oracle"]    == 10


# =====================================================================
# constant.py
# =====================================================================

def test_constant_returns_same_decision_on_any_input(tmp_io):
    decisions = set()
    for case in (_CASE_GROWTH, _CASE_SCALE, _CASE_IDEA):
        inp, out = tmp_io(case)
        d = _run_anchor("constant", inp, out)
        decisions.add(d["stage_assessment"])
    assert len(decisions) == 1, f"expected constant; got {decisions}"


def test_constant_is_deterministic(tmp_io):
    """Two invocations on identical input produce identical output."""
    inp, out = tmp_io(_CASE_GROWTH)
    d1 = _run_anchor("constant", inp, out)
    d2 = _run_anchor("constant", inp, out)
    assert d1 == d2


# =====================================================================
# brittle.py
# =====================================================================

def test_brittle_flips_when_first_header_changes(tmp_io):
    """Brittle routes off the first `## <header>`. Reorder-style
    swaps that change the first header MUST flip the decision."""
    gate_first = "## Gate Rule\nAll conditions are met.\n## Venture Description\nstuff.\n"
    venture_first = "## Venture Description\nstuff.\n## Gate Rule\nAll conditions are met.\n"
    g_in, g_out = tmp_io(gate_first)
    v_in, v_out = tmp_io(venture_first)
    g = _run_anchor("brittle", g_in, g_out)
    v = _run_anchor("brittle", v_in, v_out)
    # Different first header → different decision.
    assert g["stage_assessment"] != v["stage_assessment"]
    # Specifically: gate-rule-first → growth; venture-first → pre-seed.
    assert g["stage_assessment"] == "growth"
    assert v["stage_assessment"] == "pre-seed"


def test_brittle_is_deterministic(tmp_io):
    inp, out = tmp_io(_CASE_GROWTH)
    d1 = _run_anchor("brittle", inp, out)
    d2 = _run_anchor("brittle", inp, out)
    assert d1 == d2


# =====================================================================
# mid_issue.py — non-deterministic by design
# =====================================================================

def test_mid_issue_is_stochastic(tmp_io):
    """Mid_issue has 10% drift. Across N=80 trials the probability of
    identical output is (~0.9)^80 ≈ 2e-4; expect ≥2 distinct decisions."""
    inp, out = tmp_io(_CASE_GROWTH)
    decisions = []
    for _ in range(80):
        d = _run_anchor("mid_issue", inp, out)
        decisions.append(d["stage_assessment"])
    assert len(set(decisions)) >= 2, (
        "mid_issue produced identical output 80 times — drift rate may "
        "be too low"
    )


def test_mid_issue_inverts_traction_axis(tmp_io):
    """Wrong-direction sensitivity: a case with positive traction
    signals (paying subscribers, annual revenue) should NOT be routed
    to growth. Verified across many trials to average out drift."""
    from collections import Counter
    inp, out = tmp_io(_CASE_GROWTH)
    decisions = []
    for _ in range(30):
        d = _run_anchor("mid_issue", inp, out)
        decisions.append(d["stage_assessment"])
    # Modal decision should NOT be 'growth' for this revenue-positive case
    # (grounded would say growth; mid_issue inverts).
    most_common = Counter(decisions).most_common(1)[0][0]
    assert most_common != "growth", (
        f"mid_issue's modal decision was 'growth'; the inverted-traction "
        f"design should push it elsewhere. Got distribution: {Counter(decisions)}"
    )


def test_mid_issue_baseline_decision_within_rule_ladder(tmp_io):
    """Output (drifted or not) is one of the canonical stage labels."""
    valid = {"idea", "pre-seed", "seed", "growth", "scale"}
    inp, out = tmp_io(_CASE_GROWTH)
    for _ in range(5):
        d = _run_anchor("mid_issue", inp, out)
        assert d["stage_assessment"] in valid


# =====================================================================
# one_moderate_issue.py
# =====================================================================

def test_one_moderate_issue_is_deterministic(tmp_io):
    """one_moderate_issue is deterministic (no drift)."""
    inp, out = tmp_io(_CASE_GROWTH)
    d1 = _run_anchor("one_moderate_issue", inp, out)
    d2 = _run_anchor("one_moderate_issue", inp, out)
    assert d1 == d2


def test_one_moderate_issue_ignores_conditions_status(tmp_io):
    """Toggling 'all conditions are met' vs 'some conditions are met'
    should NOT change the decision — that's the missing axis."""
    base = (
        "## Traction Signal\nPaying subscribers, annual revenue $1M.\n"
        "## Gate Rule\nAll conditions are met.\n"
    )
    swapped = base.replace("All conditions are met", "Some conditions are met")
    a_in, a_out = tmp_io(base)
    b_in, b_out = tmp_io(swapped)
    a = _run_anchor("one_moderate_issue", a_in, a_out)
    b = _run_anchor("one_moderate_issue", b_in, b_out)
    assert a == b, (
        f"one_moderate_issue should ignore conditions-status; "
        f"got base={a}, swapped={b}"
    )


def test_one_moderate_issue_responds_to_revenue_language(tmp_io):
    """one_moderate_issue still reads non-broken axes — revenue
    language drives the decision."""
    revenue = "## Gate Rule\nAll conditions are met.\n## Traction Signal\nAnnual revenue $1M.\n"
    no_revenue = "## Gate Rule\nAll conditions are met.\n## Traction Signal\nLow signal.\n"
    r_in, r_out = tmp_io(revenue)
    n_in, n_out = tmp_io(no_revenue)
    r = _run_anchor("one_moderate_issue", r_in, r_out)
    n = _run_anchor("one_moderate_issue", n_in, n_out)
    assert r["stage_assessment"] != n["stage_assessment"]




# =====================================================================
# grounded_oracle.py
# =====================================================================

def test_grounded_oracle_is_deterministic(tmp_io):
    inp, out = tmp_io(_CASE_GROWTH)
    d1 = _run_anchor("grounded_oracle", inp, out)
    d2 = _run_anchor("grounded_oracle", inp, out)
    assert d1 == d2


def test_grounded_oracle_routes_idea(tmp_io):
    inp, out = tmp_io(_CASE_IDEA)
    d = _run_anchor("grounded_oracle", inp, out)
    assert d["stage_assessment"] == "idea"


def test_grounded_oracle_routes_growth(tmp_io):
    inp, out = tmp_io(_CASE_GROWTH)
    d = _run_anchor("grounded_oracle", inp, out)
    # Growth: conditions met + paying subscribers + annual revenue.
    assert d["stage_assessment"] == "growth"


def test_grounded_oracle_responds_to_conditions_status(tmp_io):
    """Unlike one_moderate_issue, grounded SHOULD respond to the
    conditions-status toggle — that's the axis it tracks correctly."""
    met = (
        "## Gate Rule\nAll conditions are met.\n"
    )
    unmet = (
        "## Gate Rule\nNone of these conditions are currently met.\n"
    )
    m_in, m_out = tmp_io(met)
    u_in, u_out = tmp_io(unmet)
    m = _run_anchor("grounded_oracle", m_in, m_out)
    u = _run_anchor("grounded_oracle", u_in, u_out)
    assert m["stage_assessment"] != u["stage_assessment"]
    assert u["stage_assessment"] == "idea"
