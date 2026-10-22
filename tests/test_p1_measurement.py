import io
import json
from pathlib import Path

import pytest

from owin import baseline, cli, evaluate, tokenfactory as tf
from owin.extract import parse_json, select_text, validate
from owin.schema import SchemaError, coerce
from owin.textnorm import html_to_text, is_verbatim, match_form, strip_markdown

ROOT = Path(__file__).resolve().parent.parent

SUPABASE_MD = ("Customer shall notify Supabase if it objects to the proposed change by providing Supabase with written "
               "notice of the objection within five (5) days after Supabase has provided notice to Customer of such "
               "proposed change (an “**Objection**”).")


def raw(window_type="window", days=5, **kw):
    d = {"window_type": window_type, "window_days": days, "unit": "unspecified", "clock_start": "notice",
         "clock_start_text": "notice", "remedy": "terminate", "deemed_consent_if_silent": False,
         "quote": "within five (5) days after Supabase has provided notice to Customer"}
    d.update(kw)
    return d


# Text normalisation and the verbatim gate

def test_markdown_emphasis_does_not_break_verbatim():
    quote = 'within five (5) days after Supabase has provided notice to Customer of such proposed change (an "Objection").'
    assert is_verbatim(quote, SUPABASE_MD)


def test_strip_markdown_keeps_link_text_and_drops_anchors():
    assert strip_markdown("see [privacy@vercel.com](mailto:privacy@vercel.com)\n### 6.3 Updates[#](#63-x)") == \
        "see privacy@vercel.com\n6.3 Updates"


def test_paraphrase_is_not_verbatim():
    assert not is_verbatim("Customer has five days to object after notice from Supabase.", SUPABASE_MD)


def test_short_quote_is_rejected():
    assert not is_verbatim("five (5) days", SUPABASE_MD)


def test_html_to_text_skips_scripts():
    t = html_to_text("<html><head><script>var x=1</script></head><body><p>Customer may object</p><p>within 30 days.</p></body></html>")
    assert "var x" not in t and "Customer may object" in t and match_form(t).endswith("within 30 days.")


# Schema (fixed contract)

def test_exit_only_forces_na_unit_and_clock():
    t = coerce(raw("exit_only", None, unit="unspecified", clock_start="notice"))
    assert (t.unit, t.clock_start, t.window_days) == ("n/a", "n/a", None)


@pytest.mark.parametrize("bad", [
    raw("window", None), raw("exit_only", 30), raw(window_type="maybe"), raw(unit="weeks"),
    raw(deemed_consent_if_silent="yes"), raw(days=0), raw(clock_start="whenever")])
def test_schema_rejects_incoherent_output(bad):
    with pytest.raises(SchemaError):
        coerce(bad)


def test_none_always_holds():
    t = validate(coerce(raw("none", None, quote="")), SUPABASE_MD)
    assert t.status == "held" and t.hold_reasons


def test_unverifiable_quote_holds():
    t = validate(coerce(raw(quote="Customer may object within five days of any notice whatsoever.")), SUPABASE_MD)
    assert t.status == "held" and "verbatim" in t.hold_reasons[0]


def test_verbatim_quote_passes():
    t = validate(coerce(raw(quote="within five (5) days after Supabase has provided notice to Customer of such proposed change")), SUPABASE_MD)
    assert t.status == "ok" and t.quote_verbatim


def test_parse_json_handles_fences():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json("no json here") is None


def test_select_text_keeps_clause_in_long_documents():
    filler = "\n\n".join(f"Section {i}. Unrelated boilerplate about billing and support." for i in range(2000))
    doc = filler + "\n\nCustomer may object to a new Sub-processor within ten (10) days of notice.\n\n" + filler
    text, mode = select_text(doc)
    assert mode == "keyword-windows" and "ten (10) days" in text and len(text) <= 24000


# Baseline

def test_baseline_finds_simple_window_but_cannot_say_exit_only():
    aws_like = ("At least 30 days before AWS engages a Sub-processor, AWS will update the website. To object to a "
                "Sub-processor, Customer can: (i) terminate the Agreement; or (ii) cease using the Service.")
    t = baseline.extract(aws_like)
    assert t.window_type == "window" and t.window_days == 30  # the documented failure mode


# Scoring

def test_is_exact_requires_verbatim_quote_and_all_fields():
    gold = {"window_type": "window", "window_days": 5, "unit": "unspecified", "clock_start": "notice",
            "deemed_consent_if_silent": False}
    terms = {**gold, "quote_verbatim": True, "status": "ok"}
    assert evaluate.is_exact(terms, gold)
    assert not evaluate.is_exact({**terms, "quote_verbatim": False}, gold)
    assert not evaluate.is_exact({**terms, "deemed_consent_if_silent": True}, gold)
    neg = {"window_type": "none", "window_days": None, "unit": "n/a", "clock_start": "n/a", "deemed_consent_if_silent": False}
    assert evaluate.is_exact({**neg, "status": "held"}, neg)
    assert not evaluate.is_exact(None, gold)


def test_recorded_runs_reproduce_published_headline():
    """`owin eval score` recomputes the README number from the recorded runs, with no API key."""
    published = json.loads((ROOT / "eval" / "latest-score.json").read_text())
    res = evaluate.score(evaluate.headline_runs())
    model_keys = [k for k in published["headline"] if not k.startswith("baseline")]
    assert {k: res["headline"][k] for k in model_keys} == {k: published["headline"][k] for k in model_keys}
    assert res["per_successful_run"] == published["per_successful_run"]
    assert res["headline"]["labelled_vendors_exact_majority"] == "10/10"  # acceptance bar is >= 8/10


def test_corpus_has_negative_controls_and_heldout():
    kinds = [i["kind"] for i in evaluate.load_corpus()]
    assert kinds.count("labelled") == 10 and kinds.count("negative") >= 2 and kinds.count("heldout") >= 5


# Token Factory client: usage ledger, no key leakage, budget cap

class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_chat_logs_usage_without_the_key(monkeypatch, tmp_path):
    monkeypatch.setenv("TOKEN_FACTORY_API_KEY", "sk-test-SECRET")
    monkeypatch.setattr(tf, "LEDGER", tmp_path / "usage.jsonl")
    body = {"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 500}}
    monkeypatch.setattr(tf.urllib.request, "urlopen", lambda req, timeout: _Resp(json.dumps(body).encode()))
    c = tf.chat("hi", purpose="test")
    assert c.cost_usd == pytest.approx(1000 / 1e6 * 0.30 + 500 / 1e6 * 0.90)
    log = (tmp_path / "usage.jsonl").read_text()
    assert "SECRET" not in log and '"purpose": "test"' in log


def test_eval_run_refuses_over_budget(monkeypatch, tmp_path, capsys):
    led = tmp_path / "usage.jsonl"
    led.write_text(json.dumps({"cost_usd": 3.5}) + "\n")
    monkeypatch.setattr(tf, "LEDGER", led)
    monkeypatch.setattr(evaluate, "run", lambda **k: pytest.fail("must not call the API over budget"))
    assert cli.main(["eval", "run", "--budget", "3"]) == 2
