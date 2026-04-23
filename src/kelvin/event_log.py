"""Structured event logging for Kelvin.

Emits events in either plain-text (default) or JSON-line format. Text
mode preserves v0.2-equivalent human-readable output. JSON mode writes
one record per line with a stable schema for machine consumption.

Default streams: info → stdout, warn/error → stderr. Test harnesses can
redirect either stream for capture. The `text_fallback` callable lets
legacy `echo=` consumers (e.g., tests using `list.append`) keep working
in text mode without changes.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, TextIO

# JSON log record schema version. Bumped when the shape of emitted records
# changes incompatibly. Stable at 1 for 0.2.1 — the record fields are:
#   {schema_version, ts, level, event, [text], ...extra_fields}
_SCHEMA_VERSION = 1


@dataclass
class EventLogger:
    fmt: str = "text"
    stdout: TextIO | None = None
    stderr: TextIO | None = None
    text_fallback: Callable[[str], None] | None = None
    _clock: Callable[[], float] = field(default=time.time)

    def __post_init__(self) -> None:
        if self.fmt not in ("text", "json"):
            raise ValueError(
                f"EventLogger.fmt must be 'text' or 'json', got {self.fmt!r}"
            )
        if self.stdout is None:
            self.stdout = sys.stdout
        if self.stderr is None:
            self.stderr = sys.stderr

    def info(self, event: str, *, text: str | None = None, **fields: Any) -> None:
        """Info-level event → stdout (or text_fallback in text mode)."""
        self._emit("info", event, text, fields, self.stdout)

    def warn(self, event: str, *, text: str | None = None, **fields: Any) -> None:
        """Warn-level event → stderr."""
        self._emit("warn", event, text, fields, self.stderr)

    def error(self, event: str, *, text: str | None = None, **fields: Any) -> None:
        """Error-level event → stderr."""
        self._emit("error", event, text, fields, self.stderr)

    def _emit(
        self,
        level: str,
        event: str,
        text: str | None,
        fields: dict[str, Any],
        stream: TextIO,
    ) -> None:
        if self.fmt == "json":
            record: dict[str, Any] = {
                "schema_version": _SCHEMA_VERSION,
                "ts": self._clock(),
                "level": level,
                "event": event,
            }
            if text is not None:
                record["text"] = text
            # Explicit fields take precedence over reserved keys if collided.
            for k, v in fields.items():
                record[k] = v
            stream.write(json.dumps(record, default=str) + "\n")
            stream.flush()
            return

        # Text mode — human-readable.
        line = text if text is not None else _synthesize_text(event, fields)
        if level == "info" and self.text_fallback is not None:
            # Preserve legacy `echo=list.append` consumers in tests.
            self.text_fallback(line)
        else:
            stream.write(line + "\n")
            stream.flush()


def _synthesize_text(event: str, fields: dict[str, Any]) -> str:
    """Fallback text when a structured event has no explicit text."""
    if not fields:
        return event
    pairs = " ".join(f"{k}={v}" for k, v in fields.items())
    return f"{event}: {pairs}"


def text_logger_for(echo: Callable[[str], None] | None) -> EventLogger:
    """Build a text-mode logger that routes info events through `echo`.

    Convenience for the back-compat path: callers that previously passed
    `echo=list.append` (tests) or `echo=typer.echo` (CLI) can keep doing
    so without knowing about EventLogger.
    """
    return EventLogger(fmt="text", text_fallback=echo)
