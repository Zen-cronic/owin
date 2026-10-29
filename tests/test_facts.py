"""Claims ledger: every number in README.md and on /judge is recomputed here and fails on drift."""
import json
import re

import pytest

from owin import facts, webui

README = (facts.ROOT / "README.md").read_text()


@pytest.mark.parametrize("fact", facts.FACTS, ids=[f[0] for f in facts.FACTS])
def test_fact_recomputes(fact):
    fid, _, expected, _, fn = fact
    assert fn() == expected, fid


def test_facts_md_is_current():
    assert facts.FACTS_MD.read_text() == facts.render(), "run `owin facts write`"


def _f(fid):
    return next(f[2] for f in facts.FACTS if f[0] == fid)


def test_readme_line_one_matches_the_ledger():
    line1 = README.split("\n")[2]
    auto, cells = _f("sel.auto").split("/")
    right, _ = _f("sel.correct").split("/")
    maj = _f("sel.majority").split("/")[0]
    assert f"filled {auto} of {cells}" in line1 and f"got {right} right" in line1
    assert f"other {_f('sel.confirm')}" in line1 and f"only {maj} times" in line1
    assert f"On {_f('sel.vendors')} AI vendors" in line1 and "`v3fresh`" in line1 and f"{_f('sel.items')} features" in line1


def test_readme_numbers_match_the_ledger():
    for fid in ("sel.auto", "sel.correct", "sel.majority", "v3.items", "v3.base", "v2.old", "v1.prereg"):
        assert _f(fid) in README, fid
    assert f"${_f('cost.call')} per reading" in README
    assert f"about **${round(_f('cost.feature'), 3)}**" in README
    assert f"mean {round(_f('lat.mean'), 1)} s, p95 {round(_f('lat.p95'), 1)} s" in README
    assert "80/90" in README and "77/80" in README and "77/90" in README and "72/77" in README
    assert _f("model") in README and _f("demo.quote").split(" is ")[1].rstrip(".") in README
    assert _f("v3.passed") is False and "fails our own 80% bar" in README
    # The numbers the README carries outside the headline table: all in the ledger, all recomputed.
    assert f"{_f('v3.calls')} calls" in README and f"${_f('v3.cost.total')} total" in README
    assert f"${_f('price.super').replace(' / ', ' / $')} per M tokens" in README
    assert f"{_f('dpa.runs')} runs" in README and f"{_f('dpa.neg')} thin-evidence controls" in README
    assert f"{_f('sweep.vendors')}-vendor" in README or f"{_f('sweep.vendors')} vendors" in README
    assert f"{_f('sel.swing')} points" in README


def test_judge_page_reads_its_numbers_from_the_api():
    js = (webui.WEB / "judge.js").read_text()
    html = (webui.WEB / "judge.html").read_text()
    assert "/api/selective" in js
    # No hard-coded headline numbers on the judge page: they are recomputed on load.
    assert not re.search(r"\b(27|26|33)\b", html + js)


def test_copy_rules():
    for name, text in (("README.md", README), ("FACTS.md", facts.FACTS_MD.read_text()),
                       ("judge.html", (webui.WEB / "judge.html").read_text()), ("app.js", (webui.WEB / "app.js").read_text())):
        low = text.lower()
        assert "compliant" not in low, name
        assert "open source" not in low and "open-source" not in low, name
        assert not re.search(r"added cloudflare", low), name
    assert "open-weight" in README and "not legal advice" in README.lower()
    assert "changed Cloudflare's entry and added OAI International" in README


def test_number_badge_is_the_recomputed_headline():
    url = facts.badge_url()
    assert url in README  # the badge a reader sees is the number this suite recomputes
    h = facts._sel()["headline"]
    assert h["auto_correct"].replace("/", "%2F") in url


def test_thinking_comparison_is_recomputed_and_the_readme_says_it():
    assert json.loads(facts.THINKING_JSON.read_text()) == facts.thinking()
    th = facts.thinking()
    assert th["live_path_reasoning"] == "on"  # the off arm made confident misses the on arm did not
    assert th["off"]["confident_misses"] > th["on"]["confident_misses"]
    off_auto, off_right = _f("think.off").split(", ")
    assert f"{off_right.split('/')[0]} of {off_right.split('/')[1]}" in README
