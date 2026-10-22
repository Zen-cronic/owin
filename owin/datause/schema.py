"""DataUseTerms: what a vendor's own page says about one AI feature (data contract v1, Pivot A).

One field per security-questionnaire question, so the answer pack (A3) can fill
each question from one field plus its verbatim quote:

| questionnaire question                                          | field(s)                                   |
|-----------------------------------------------------------------|--------------------------------------------|
| Is our data used to train the provider's models?                | used_for_training + training_quote         |
| How long does the provider retain prompts and outputs?          | retention_days, retention_condition + retention_quote |
| Is zero data retention (ZDR) available for this feature?        | zdr + zdr_quote                            |
| Where is the data processed / stored?                           | region + region_quote                      |
| Which other parties (model provider, reviewers) can see it?     | third_party_access + third_party_quote     |

The model proposes; `validate` decides. A field the model asserts without a
verbatim quote from the page is downgraded to null/"unspecified" and recorded in
`hold_reasons`, so an answer never reaches a questionnaire without its sentence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

Training = Literal["yes", "no", "opt_in", "opt_out", "unspecified"]
Zdr = Literal["available", "not_available", "excluded", "unspecified"]
ThirdParty = Literal["yes", "no", "unspecified"]

TRAINING = ("yes", "no", "opt_in", "opt_out", "unspecified")
ZDR = ("available", "not_available", "excluded", "unspecified")
THIRD_PARTY = ("yes", "no", "unspecified")

# The headline: all three must equal the gold label (and every asserted one must carry a verbatim quote).
SCORED_FIELDS = ("retention_days", "used_for_training", "zdr")
# Field -> the quote that must justify it when it is asserted.
QUOTE_OF = {"retention_days": "retention_quote", "used_for_training": "training_quote", "zdr": "zdr_quote",
            "region": "region_quote", "third_party_access": "third_party_quote"}

# The labelling rules. The prompt states the same rules; the label audit cites them.
LABEL_RULES = {
    "retention_days": ("The longest stated period, in days, for which the vendor keeps customer content (prompts, outputs, "
                       "files) from THIS feature under the default arrangement (no ZDR). Abuse-monitoring and reliability "
                       "logs count. Content flagged as violating policy, legal holds and model-specific exceptions do not, "
                       "unless the feature IS that case. 0 when the page says the content is not retained by default. null "
                       "when content stays until the customer deletes it, when no number is stated, or when the page is "
                       "silent. Years x 365."),
    "used_for_training": ("yes = the page says this feature's content is used to train/improve models with no opt-out "
                          "stated; opt_out = used by default but the customer can opt out; opt_in = not used unless the "
                          "customer opts in, shares, or gives permission; no = not used, with no way to opt in "
                          "mentioned; unspecified = the page does not say. Product or service improvement counts as use: "
                          "when the page says content may be used for product improvement (or training) by default and "
                          "the customer can turn that off, the label is opt_out, even if a narrower use such as 'training "
                          "other models' is separately opt-in. The label follows the broadest use that is on by default "
                          "(rule added 2026-10-21 after the v2 run; it changed one label, together-serverless)."),
    "zdr": ("available = the page says zero data retention (or a named control under which the vendor stores no "
            "prompts/outputs, e.g. Azure 'modified abuse monitoring') can apply to this feature, including on approval; "
            "excluded = ZDR exists but this feature is not covered or cannot run under it; not_available = the vendor "
            "says it offers no ZDR; unspecified = the page does not say for this feature (a link elsewhere is not an answer)."),
    "region": "Free text: where content is processed or stored, as the page states it. Not scored.",
    "third_party_access": "yes/no: whether the page says parties other than the vendor see the content. Not scored.",
}


@dataclass
class DataUseTerms:
    retention_days: int | None
    retention_condition: str
    retention_quote: str
    used_for_training: Training
    training_quote: str
    zdr: Zdr
    zdr_quote: str
    region: str
    region_quote: str
    third_party_access: ThirdParty
    third_party_quote: str
    # Set by validation, not by the model.
    verbatim: dict = field(default_factory=dict)
    status: Literal["ok", "partial", "no_terms"] = "no_terms"
    hold_reasons: list[str] = field(default_factory=list)
    model_claimed: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def scored(self) -> dict:
        return {k: getattr(self, k) for k in SCORED_FIELDS}


class SchemaError(ValueError):
    pass


def _s(raw: dict, k: str) -> str:
    v = raw.get(k)
    return "" if v is None else str(v)


def coerce(raw: dict) -> DataUseTerms:
    if not isinstance(raw, dict):
        raise SchemaError("not an object")
    rd = raw.get("retention_days")
    if isinstance(rd, str):
        rd = int(rd.strip()) if rd.strip().isdigit() else (None if rd.strip().lower() in ("", "null", "none") else rd)
    if rd is not None and not (isinstance(rd, int) and not isinstance(rd, bool) and 0 <= rd <= 3650):
        raise SchemaError(f"retention_days {rd!r}")
    # An empty or missing enum is the absence of an answer, never a guess.
    tr = raw.get("used_for_training") or "unspecified"
    if tr not in TRAINING:
        raise SchemaError(f"used_for_training {tr!r}")
    z = raw.get("zdr") or "unspecified"
    if z not in ZDR:
        raise SchemaError(f"zdr {z!r}")
    tp = raw.get("third_party_access") or "unspecified"
    if tp not in THIRD_PARTY:
        raise SchemaError(f"third_party_access {tp!r}")
    region = _s(raw, "region") or "unspecified"
    return DataUseTerms(rd, _s(raw, "retention_condition"), _s(raw, "retention_quote"), tr, _s(raw, "training_quote"),
                        z, _s(raw, "zdr_quote"), region, _s(raw, "region_quote"), tp, _s(raw, "third_party_quote"))


def asserted(t: DataUseTerms | dict, f: str) -> bool:
    v = t[f] if isinstance(t, dict) else getattr(t, f)
    return v is not None and v != "unspecified"
