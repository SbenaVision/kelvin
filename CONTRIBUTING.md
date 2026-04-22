# Contributing to Kelvin

Kelvin is under active development on the v0.2 roadmap. Before opening a pull request, please open a GitHub issue first so we can discuss scope and point you at context or ongoing work. Issues, design feedback, bug reports, and docs corrections are all welcome; PRs that overlap with in-progress roadmap items may be held until the current cycle completes, so a quick check-in saves both sides time. The current roadmap lives in the pinned **v0.2 roadmap — work in progress** issue, and in-flight tiers are visible on the PR list as drafts titled `WIP: Tier N — …`.

## Running locally

```bash
pip install -e '.[dev]'
pytest
```

Tests live under `tests/`; the runner and case-file format are described in [docs/kelvinspec.md](docs/kelvinspec.md). The whitepaper at [docs/whitepaper.md](docs/whitepaper.md) formalizes the method and names its current limits explicitly — those limits are what the v0.2 and v0.3 milestones address.

## Questions

Open an issue — the maintainer watches the tracker directly.
