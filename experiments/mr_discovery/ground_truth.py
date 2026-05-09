"""Ground-truth MRs for the toy pipeline.

Derived by inspection of `pipeline.score`. These are the MRs the
discovery procedure *should* find. Used to compute recall and precision.

Format: (transformation_name, relation_name, status)

status ∈ {"valid", "bug_symmetry"}:
- "valid": a genuine MR — must be discovered and retained.
- "bug_symmetry": holds because the field is ignored — must be discovered
  by the empirical loop, then rejected by the bug-symmetry filter.

NOT listed here: pairs that depend on the input (e.g., R_le for
scale_revenue_up only holds when the revenue change crosses a tier
boundary upward, which it does by construction; we include it as valid).
We pre-register here only the MRs that should hold *universally* on
valid corpus inputs.
"""
from __future__ import annotations


GROUND_TRUTH: list[tuple[str, str, str]] = [
    # --- Invariances (R_eq) ---
    ("permute_founders",    "R_eq", "valid"),
    ("rename_founders",     "R_eq", "valid"),
    ("permute_risks",       "R_eq", "valid"),

    # Bug-symmetry traps: description is never read
    ("append_description",  "R_eq", "bug_symmetry"),
    ("replace_description", "R_eq", "bug_symmetry"),

    # --- Monotone-up (R_le: score non-decreasing) ---
    ("bump_founder_experience", "R_le", "valid"),  # avg up, capped
    ("scale_revenue_up",        "R_le", "valid"),  # revenue tier non-decreasing
    ("team_plus",               "R_le", "valid"),  # team bonus non-decreasing (capped)
    ("promote_stage",           "R_le", "valid"),  # stage weight non-decreasing
    ("drop_risk",               "R_le", "valid"),  # fewer risks → penalty non-increasing

    # --- Monotone-down (R_ge: score non-increasing) ---
    ("scale_revenue_down",      "R_ge", "valid"),
    ("team_minus",              "R_ge", "valid"),
    ("demote_stage",            "R_ge", "valid"),
    ("add_risk",                "R_ge", "valid"),  # more risks → penalty non-decreasing (capped)
]


def valid_mrs() -> list[tuple[str, str]]:
    return [(t, r) for t, r, s in GROUND_TRUTH if s == "valid"]


def bug_symmetry_mrs() -> list[tuple[str, str]]:
    return [(t, r) for t, r, s in GROUND_TRUTH if s == "bug_symmetry"]
