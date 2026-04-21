"""Parse markdown cases into `Case` objects."""

from __future__ import annotations

import re
from pathlib import Path

from kelvin.types import Case, Unit

_HEADER_RE = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.MULTILINE)


def normalize_type(raw: str) -> str:
    """Lowercase, trim, collapse whitespace runs to single underscore."""
    return "_".join(raw.strip().lower().split())


def parse_case(path: Path) -> Case:
    """Parse one markdown file into a `Case`."""
    text = path.read_text(encoding="utf-8")
    matches = list(_HEADER_RE.finditer(text))

    name = path.stem

    if not matches:
        preamble = text.strip()
        return Case(name=name, source_path=path, preamble=preamble, units=[])

    preamble = text[: matches[0].start()].strip()

    units: list[Unit] = []
    for i, match in enumerate(matches):
        header_raw = match.group(1)
        body_start = match.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()
        units.append(
            Unit(
                type=normalize_type(header_raw),
                content=body,
                raw_header=header_raw.strip(),
                index=i,
            )
        )

    return Case(name=name, source_path=path, preamble=preamble, units=units)


def render_case(preamble: str, units: list[Unit]) -> str:
    """Render a (possibly perturbed) case back to markdown.

    Preamble is pinned at the top; units follow in the order given.
    """
    parts: list[str] = []
    if preamble:
        parts.append(preamble)
    for u in units:
        parts.append(f"## {u.raw_header}\n\n{u.content}".rstrip())
    body = "\n\n".join(parts)
    return body + "\n" if body and not body.endswith("\n") else body


def load_cases(cases_dir: Path) -> list[Case]:
    """Parse every `*.md` file in `cases_dir` (non-recursive), sorted by name."""
    if not cases_dir.exists():
        return []
    return [parse_case(p) for p in sorted(cases_dir.glob("*.md"))]


def discover_unit_types(cases_dir: Path) -> list[str]:
    """Return sorted, unique list of normalized unit types found in `cases_dir`.

    Used by `kelvin init` to offer a multi-select for governing types.
    """
    types: set[str] = set()
    for case in load_cases(cases_dir):
        for u in case.units:
            types.add(u.type)
    return sorted(types)
