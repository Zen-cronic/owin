"""The fixed extraction schema (data contract v1). See docs/CONTRACT.md."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

WindowType = Literal["window", "exit_only", "none"]
Unit = Literal["calendar", "business", "unspecified", "n/a"]
ClockStart = Literal["notice", "page_update", "other", "n/a"]

WINDOW_TYPES = ("window", "exit_only", "none")
UNITS = ("calendar", "business", "unspecified", "n/a")
CLOCK_STARTS = ("notice", "page_update", "other", "n/a")

# Fields that must all equal the gold label for a run to count as "exact".
SCORED_FIELDS = ("window_type", "window_days", "unit", "clock_start", "deemed_consent_if_silent")


@dataclass
class WindowTerms:
    """What a vendor's DPA says about objecting to a NEW sub-processor.

    Produced by the model, then validated: a term set whose quote is not found
    verbatim in the source is never used by the decision layer (status "held").
    """

    window_type: WindowType
    window_days: int | None
    unit: Unit
    clock_start: ClockStart
    clock_start_text: str
    remedy: str
    deemed_consent_if_silent: bool
    quote: str
    # Set by validation, not by the model.
    quote_verbatim: bool = False
    status: Literal["ok", "held"] = "held"
    hold_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def scored(self) -> dict:
        return {k: getattr(self, k) for k in SCORED_FIELDS}


class SchemaError(ValueError):
    pass


def coerce(raw: dict) -> WindowTerms:
    """Coerce a model's JSON object into WindowTerms, or raise SchemaError."""
    if not isinstance(raw, dict):
        raise SchemaError("not an object")
    wt = raw.get("window_type")
    if wt not in WINDOW_TYPES:
        raise SchemaError(f"window_type {wt!r}")
    wd = raw.get("window_days")
    if isinstance(wd, str) and wd.strip().isdigit():
        wd = int(wd.strip())
    if wd is not None and not (isinstance(wd, int) and not isinstance(wd, bool) and 0 < wd < 400):
        raise SchemaError(f"window_days {wd!r}")
    unit = raw.get("unit")
    if unit not in UNITS:
        raise SchemaError(f"unit {unit!r}")
    cs = raw.get("clock_start")
    if cs not in CLOCK_STARTS:
        raise SchemaError(f"clock_start {cs!r}")
    dc = raw.get("deemed_consent_if_silent")
    if not isinstance(dc, bool):
        raise SchemaError(f"deemed_consent_if_silent {dc!r}")
    # Internal consistency: the schema, not the model, decides what is coherent.
    if wt == "window" and wd is None:
        raise SchemaError("window without window_days")
    if wt != "window" and wd is not None:
        raise SchemaError(f"{wt} with window_days")
    if wt != "window":
        # A unit or clock is meaningless without a deadline; fix it in code, not by re-asking.
        unit, cs = "n/a", "n/a"
    return WindowTerms(
        window_type=wt,
        window_days=wd,
        unit=unit,
        clock_start=cs,
        clock_start_text=str(raw.get("clock_start_text") or ""),
        remedy=str(raw.get("remedy") or ""),
        deemed_consent_if_silent=dc,
        quote=str(raw.get("quote") or ""),
    )
