"""P1 selective answering: auto-answer a cell only when every successful run agrees on it (at least 2; errored runs abstain); otherwise ask a person."""
import json

import pytest

from owin import cli
from owin.datause import pack, registry, selective


def test_agreement_is_strict():
    a = {"zdr": "excluded", "zdr_quote": "q1"}
    assert selective.agreement([a, a, a], "zdr")["state"] == "auto"
    b = {"zdr": "unspecified", "zdr_quote": ""}
    r = selective.agreement([a, b, a], "zdr")
    assert r["state"] == "confirm" and r["runs_agreeing"] == "2/3" and r["majority"] == "excluded"
    assert [o["value"] for o in r["options"]] == ["excluded", "unspecified"] and r["options"][0]["quote"] == "q1"
    # An errored run abstains: two successful readings that agree are enough.
    r = selective.agreement([a, None, a], "zdr")
    assert r["state"] == "auto" and r["value"] == "excluded" and r["runs_agreeing"] == "2/2"
    assert (r["readings_ok"], r["readings_failed"], r["readings_total"]) == (2, 1, 3)
    # ...but one successful reading is never enough, and an errored run never counts as a value.
    assert selective.agreement([a, None, None], "zdr")["state"] == "confirm"
    assert selective.agreement([None, None, None], "zdr")["state"] == "confirm"
    r = selective.agreement([a, None, b], "zdr")
    assert r["state"] == "confirm" and r["runs_agreeing"] == "1/2" and [o["value"] for o in r["options"]] == ["excluded", "unspecified"]


def test_errored_run_abstains_in_pack_too():
    """Same rule in the pack: a field whose successful readings agree reaches the rule even if a run failed."""
    a = {"zdr": "excluded", "zdr_quote": "The MCP connector is not covered by ZDR arrangements."}
    reg = json.loads(json.dumps(registry.load()))
    reg["anthropic-mcp-connector"]["field_agreement"]["zdr"] = {**selective.agreement([a, None, a], "zdr"), "basis": "test"}
    p = pack.build(reg=reg)
    assert next(x for x in p["answers"] if x["id"] == "Q03")["badge"] == "not_true"
    reg["anthropic-mcp-connector"]["field_agreement"]["zdr"] = {**selective.agreement([a, None, None], "zdr"), "basis": "test"}
    q3 = next(x for x in pack.build(reg=reg)["answers"] if x["id"] == "Q03")
    assert q3["badge"] == "confirm"


def test_no_special_case_left_in_pack():
    import inspect
    assert "never hides a contradiction" not in inspect.getsource(pack)


def test_v3fresh_selective_numbers_recompute_from_recorded_runs():
    r = selective.report("v3fresh")
    h = r["headline"]
    assert (h["cells"], h["items"]) == (33, 11)
    assert h["auto_answered"] == "27/33" and h["auto_correct"] == "26/27"
    assert h["sent_to_confirm"] == 6 and h["confirm_majority_right"] == "2/6"
    # The one confident miss is the self-disclosed OpenRouter label error, kept per the pre-registration.
    assert [(m["item"], m["field"], m["value"], m["gold"]) for m in h["auto_misses"]] == [
        ("openrouter-inference-zdr", "retention_days", 0, None)]
    assert h["auto_misses"][0]["footnote"] and "label error" in h["auto_misses"][0]["footnote"]
    assert r["negative_controls"]["auto_correct"] == "6/6"
    ref = r["reference_not_clean"]
    assert (ref["v3_old"]["auto_answered"], ref["v3_old"]["auto_correct"]) == ("80/90", "77/80")
    # v2 old has one errored run (anthropic-mcp-connector); it abstains, so its 3 cells auto-answer on 2/2.
    assert (ref["v2_old"]["auto_answered"], ref["v2_old"]["auto_correct"]) == ("77/90", "72/77")


def test_cli_selective(capsys):
    assert cli.main(["eval", "selective", "--corpus", "datause", "--split", "v3fresh", "--brief"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert (out["auto_answered"], out["auto_correct"], out["sent_to_confirm"], out["confirm_majority_right"]) == (
        "27/33", "26/27", 6, "2/6")


def _reg_with_disagreement(fid="anthropic-mcp-connector", field="zdr"):
    reg = json.loads(json.dumps(registry.load()))
    t = {"zdr": "excluded", "zdr_quote": "The MCP connector is not covered by ZDR arrangements."}
    u = {"zdr": "unspecified", "zdr_quote": ""}
    reg[fid]["field_agreement"][field] = {**selective.agreement([t, u, t], field), "basis": "test"}
    return reg


def test_disagreement_becomes_confirm_with_values_and_quotes():
    p = pack.build(reg=_reg_with_disagreement())
    c = next(c for c in next(a for a in p["answers"] if a["id"] == "Q03")["cells"] if c["endpoint"] == "/api/crm-sync")
    assert c["verdict"] == "confirm" and c["vendor_value"] is None
    assert c["confirm"]["runs_agreeing"] == "2/3"
    assert [o["label"] for o in c["confirm"]["options"]] == ["Not covered by ZDR", "Page does not say"]
    assert c["confirm"]["options"][0]["quote"] == "The MCP connector is not covered by ZDR arrangements."
    # The catch is no longer asserted from a split reading.
    assert p["catch"] is None and p["counts"]["confirm"] >= 1


def test_confirm_badge_on_a_swapped_stack():
    """The one split left in the catalog on v3: OpenAI's page read for Responses gives third-party access 'yes' on
    2 of 3 readings and 'unspecified' on 1. Point /api/embed at Responses and answer 5's cell asks a person."""
    m = pack.set_feature(pack.load_demo(), "/api/embed", "openai-responses")
    p = pack.build(m)
    q5 = next(a for a in p["answers"] if a["id"] == "Q05")
    c = next(c for c in q5["cells"] if c["endpoint"] == "/api/embed")
    assert c["verdict"] == "confirm" and c["confirm"]["runs_agreeing"] == "2/3" and c["vendor_value"] is None
    assert [o["value"] for o in c["confirm"]["options"]] == ["yes", "unspecified"]
    assert q5["badge"] == "stale"  # OpenAI's list change outranks the confirm on the demo's stated_at
    m["stated"]["stated_at"] = "2026-10-21"  # written after the list change: the split is what is left
    q5 = next(a for a in pack.build(m)["answers"] if a["id"] == "Q05")
    assert q5["badge"] == "confirm" and q5["badge_label"] == "Confirm" and q5["endpoints_confirm"] == 1
    assert "confirm" in q5["answer"]


def test_thin_evidence_is_held_never_invented():
    p = pack.build(pack.set_feature(pack.load_demo(), "/api/crm-sync", "thin-anthropic-rate-limits"))
    for qid in ("Q01", "Q02", "Q03", "Q04"):
        c = next(c for c in next(a for a in p["answers"] if a["id"] == qid)["cells"] if c["endpoint"] == "/api/crm-sync")
        assert c["verdict"] == "held" and c["quote"] == "" and c["thin_evidence"]
    assert p["catch"] is None


def test_region_never_auto_or_confirm():
    for e in registry.load().values():
        assert "region" not in (e.get("field_agreement") or {})
