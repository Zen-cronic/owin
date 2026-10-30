"""A1: measurement harness for AI data-use terms per feature (Pivot A)."""
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from owin import cli
from owin.datause import baseline, evaluate as dv
from owin.datause.extract import select_text, validate
from owin.datause.schema import QUOTE_OF, SCORED_FIELDS, SchemaError, asserted, coerce
from owin.textnorm import is_verbatim

ROOT = Path(__file__).resolve().parent.parent
RAW_PRESENT = (ROOT / "fixtures" / "raw" / "datause").exists()
PAGE = ("## Data retention\n\nThe **MCP connector** is not covered by ZDR arrangements. Data exchanged with MCP servers "
        "is retained according to Anthropic's standard data retention policy.\n\nRetained data is never used for model "
        "training without your express permission.")


def raw(**kw):
    d = {"retention_days": None, "retention_condition": "", "retention_quote": "", "used_for_training": "opt_in",
         "training_quote": "Retained data is never used for model training without your express permission.",
         "zdr": "excluded", "zdr_quote": "The MCP connector is not covered by ZDR arrangements.", "region": "unspecified",
         "region_quote": "", "third_party_access": "unspecified", "third_party_quote": ""}
    d.update(kw)
    return d


# Schema: one field per questionnaire question, strict enums

def test_schema_has_a_field_and_quote_per_questionnaire_question():
    assert set(QUOTE_OF) == {"retention_days", "used_for_training", "zdr", "region", "third_party_access"}
    assert SCORED_FIELDS == ("retention_days", "used_for_training", "zdr")


@pytest.mark.parametrize("bad", [raw(used_for_training="maybe"), raw(zdr="partial"), raw(retention_days=-1),
                                 raw(retention_days="thirty"), raw(third_party_access="sometimes"), "not a dict"])
def test_schema_rejects_bad_values(bad):
    with pytest.raises(SchemaError):
        coerce(bad)


def test_empty_enum_is_absence_not_guess():
    t = coerce(raw(third_party_access="", zdr=None, used_for_training=""))
    assert (t.third_party_access, t.zdr, t.used_for_training) == ("unspecified", "unspecified", "unspecified")


# Trust split: an asserted field without a verbatim quote never reaches an answer

def test_markdown_bold_does_not_break_verbatim():
    t = validate(coerce(raw()), PAGE)
    assert t.status == "ok" and t.zdr == "excluded" and t.verbatim["zdr"]


def test_paraphrased_quote_is_withheld_not_used():
    t = validate(coerce(raw(zdr_quote="MCP connector is outside zero data retention.")), PAGE)
    assert t.zdr == "unspecified" and t.model_claimed == {"zdr": "excluded"} and t.status == "partial"


def test_single_table_cell_is_not_a_quote():
    t = validate(coerce(raw(used_for_training="no", training_quote="No")), PAGE)
    assert t.used_for_training == "unspecified" and "used_for_training" in t.model_claimed


def test_nothing_asserted_is_no_terms():
    t = validate(coerce(raw(used_for_training="unspecified", training_quote="", zdr="unspecified", zdr_quote="")), PAGE)
    assert t.status == "no_terms" and not any(asserted(t, f) for f in QUOTE_OF)


def test_select_text_keeps_feature_rows_in_long_pages():
    filler = "\n\n".join(f"Navigation item {i}" for i in range(6000))
    page = filler + "\n\nEndpoint\nData used for training\nZero Data Retention eligible\n\n/v1/batches\nNo\n30 days\nUntil deleted\nNo"
    text, mode = select_text(page, "Batch API (/v1/batches)")
    assert mode == "keyword-windows" and "/v1/batches" in text and "Zero Data Retention eligible" in text


# Baseline

def test_baseline_reads_a_plain_sentence():
    t = baseline.extract("Batch processing stores request and response data for up to 29 days after batch creation.",
                         "Message Batches API (/v1/messages/batches)")
    assert (t.retention_days, t.used_for_training, t.zdr) == (29, "unspecified", "unspecified")


def test_baseline_ignores_navigation_training_links():
    assert baseline.extract("Online trainings\nTraining\nRate limits apply per minute.", "x").used_for_training == "unspecified"


# Corpus integrity (the label audit)

def test_corpus_shape_heldout_share_and_negatives():
    items = dv.load_corpus()
    held = [i for i in items if i["split"] in ("heldout", "fresh")]
    neg = [i for i in items if i["kind"] == "negative"]
    assert len(held) / len(items) >= 0.40 and len(neg) >= 4
    assert len({i["id"] for i in items}) == len(items)
    for i in neg:
        assert i["gold"] == {"retention_days": None, "used_for_training": "unspecified", "zdr": "unspecified"}


def test_every_asserted_label_has_a_justifying_sentence():
    ev_of = {"retention_days": "retention", "used_for_training": "training", "zdr": "zdr"}
    for i in dv.load_corpus():
        for f, ev in ev_of.items():
            if asserted(i["gold"], f):
                assert i["evidence"][ev], f"{i['id']}.{f} has no justifying sentence"


def test_demo_catch_items_are_in_the_corpus():
    items = {i["id"]: i for i in dv.load_corpus()}
    assert items["anthropic-mcp-connector"]["gold"]["zdr"] == "excluded"
    assert items["anthropic-batch"]["gold"]["retention_days"] == 29
    assert items["anthropic-batch"]["gold"]["zdr"] == "excluded"


def test_manifest_records_provenance_for_every_source():
    man = json.loads((ROOT / "fixtures" / "manifest.json").read_text())["datause"]
    for i in dv.load_corpus():
        m = man[i["source"]]
        assert m["url"] == i["url"] and len(m["sha256"]) == 64 and m["fetched_at"].startswith("2026-")


@pytest.mark.skipif(not RAW_PRESENT, reason="raw vendor pages are gitignored")
def test_label_evidence_is_verbatim_and_sources_unchanged():
    from owin.textnorm import sha256
    for i in dv.load_corpus():
        src = (ROOT / i["file"]).read_text()
        assert sha256(src) == i["source_sha256"], f"{i['source']} changed since labelling"
        for f, s in i["evidence"].items():
            assert not s or is_verbatim(s, src), f"{i['id']}.{f}"


# The number: recomputed from recorded runs, no key

def _committed_score() -> dict:
    return json.loads((ROOT / "eval" / "datause" / "latest-score.json").read_text())


def test_headline_recomputes_from_recorded_runs():
    res = dv.score(dv.headline_runs())
    committed = _committed_score()
    assert res["headline"] == committed["headline"]
    assert res["acceptance"] == committed["acceptance"]


def test_relabel_is_disclosed_with_before_and_after():
    """together-serverless opt_in -> opt_out (product-improvement rule, after the v2 run): 24/30 -> 23/30, below the bar."""
    before = json.loads((ROOT / "eval" / "datause" / "v2-before-relabel-score.json").read_text())
    after = dv.score(dv._headline_key("previous_headline_runs"))
    assert before["acceptance"]["positive_items_exact"] == "24/30" and before["acceptance"]["passed"]
    assert after["acceptance"]["positive_items_exact"] == "23/30" and not after["acceptance"]["passed"]
    assert after["headline"]["fresh_heldout"]["items_exact_majority"] == "4/6"
    item = next(i for i in dv.load_corpus() if i["id"] == "together-serverless")
    assert item["gold"]["used_for_training"] == "opt_out" and item["label_history"][0]["from"] == "opt_in"
    assert any(k == "together-serverless" for k, _ in dv.RELABELS)


def test_score_without_raw_fixtures_uses_recorded_validation(monkeypatch):
    monkeypatch.setattr(dv, "_source", lambda item: None)
    res = dv.score(dv.headline_runs())
    assert res["quotes_rechecked_against_source"] is False
    # With no page on disk the baseline comes from its recorded output, so the whole headline still recomputes.
    assert res["baseline"] is not None and res["headline"] == _committed_score()["headline"]


def test_preregistered_v1_run_failed_and_is_still_reported():
    v1 = json.loads((ROOT / "eval" / "datause" / "headline.json").read_text())["preregistered_run"]
    res = dv.score([ROOT / v1])
    assert res["acceptance"]["passed"] is False and res["acceptance"]["positive_items_exact"] == "16/24"


def test_demo_catch_is_measured():
    res = dv.score(dv.registry_runs())
    assert res["items"]["anthropic-mcp-connector"]["majority_exact"]
    assert res["items"]["anthropic-batch"]["majority_exact"]


def test_negative_controls_hold():
    res = dv.score(dv.headline_runs())
    neg = [v for v in res["items"].values() if v["kind"] == "negative"]
    assert sum(v["majority_exact"] for v in neg) * 4 >= 3 * len(neg)


def test_cli_score_datause_needs_no_key(monkeypatch):
    monkeypatch.delenv("TOKEN_FACTORY_API_KEY", raising=False)
    monkeypatch.setenv("OWIN_ENV_FILE", "/nonexistent")
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert cli.main(["eval", "score", "--corpus", "datause", "--brief"]) == 0
    out = json.loads(buf.getvalue())
    assert out["corpus"] == "datause" and out["prompt_versions"] == ["v3"]


def test_recorded_runs_contain_no_secret():
    for p in (ROOT / "eval" / "datause" / "runs").glob("*.json"):
        t = p.read_text()
        assert "Bearer" not in t and "TOKEN_FACTORY_API_KEY" not in t


def test_v3fresh_labels_match_the_preregistration():
    """The v3fresh split was labelled and committed before prompt v3 existed; its labels may never drift."""
    pre = json.loads((ROOT / "eval" / "datause" / "preregistration-v3.json").read_text())
    items = {i["id"]: i for i in dv.load_corpus() if i["split"] == "v3fresh"}
    assert set(items) == set(pre["items"]) and pre["positives"] >= 8 and pre["negatives"] >= 2
    for iid, gold in pre["items"].items():
        assert items[iid]["gold"] == gold, iid
        assert not items[iid].get("label_history"), iid


def _without_recheck_flag(d: dict) -> dict:
    """latest-score.json was written with the pages on disk; on a clone the verbatim gate is not re-run (the pages
    are gitignored) and the recorded gate results are used, so only this flag may differ."""
    out = {k: v for k, v in d.items() if k != "quotes_rechecked_against_source"}
    if isinstance(out.get("reference_old_corpus_not_clean"), dict):
        out["reference_old_corpus_not_clean"] = _without_recheck_flag(out["reference_old_corpus_not_clean"])
    return out


def test_v3_headline_is_the_preregistered_split_only():
    """README headline = v3 on v3fresh (labels committed before v3 existed); the old corpus is reference, labelled not clean."""
    committed = _committed_score()
    now = dv.latest()
    assert _without_recheck_flag(now) == _without_recheck_flag(committed)
    assert now["quotes_rechecked_against_source"] is RAW_PRESENT  # said, never assumed
    runs = [json.loads(p.read_text()) for p in dv.headline_runs()]
    pre = json.loads((ROOT / "eval" / "datause" / "preregistration-v3.json").read_text())
    assert all(d["prompt_version"] == "v3" and d["runs_per_item"] == 3 for d in runs)
    assert {c["id"] for d in runs for c in d["calls"]} == set(pre["items"])
    acc = committed["acceptance_v3fresh"]
    assert acc["positive_items_exact"] == "7/11" and acc["negative_items_held"] == "2/2" and acc["passed"] is False
    assert committed["headline"]["v3fresh"]["baseline_items_exact"] == "4/11"
    ref = committed["reference_old_corpus_not_clean"]
    assert "NOT a clean test" in ref["_about"] and ref["acceptance"]["positive_items_exact"] == "24/30"
    assert any(k.startswith("openrouter-inference-zdr") for k, _ in dv.POST_RUN_TENSIONS)


# The keyword baseline recomputes on a clone: its output is recorded per page sha256 (values only, no page text)

def test_recorded_baseline_covers_every_item_and_matches_the_labelled_bytes():
    rec = json.loads((ROOT / "eval" / "datause" / "baseline-outputs.json").read_text())["items"]
    corpus = dv.load_corpus()
    assert set(rec) == {i["id"] for i in corpus}
    for i in corpus:
        assert rec[i["id"]]["source_sha256"] == i["source_sha256"], i["id"]
        assert set(rec[i["id"]]) == {"source_sha256", *SCORED_FIELDS}  # structured values only


@pytest.mark.skipif(not RAW_PRESENT, reason="raw vendor pages are gitignored")
def test_recorded_baseline_equals_the_recomputed_baseline():
    rec = json.loads((ROOT / "eval" / "datause" / "baseline-outputs.json").read_text())["items"]
    for i in dv.load_corpus():
        assert {f: rec[i["id"]][f] for f in SCORED_FIELDS} == baseline.extract(dv._source(i), i["feature"]).scored(), i["id"]


def test_recorded_baseline_is_used_only_for_the_same_bytes(monkeypatch):
    item = {**dv.load_corpus()[0], "file": "fixtures/raw/does-not-exist.txt"}
    rec = {item["id"]: {"source_sha256": item["source_sha256"], "retention_days": 7, "used_for_training": "no", "zdr": "available"}}
    assert dv.baseline_output(item, recorded=rec) == {"retention_days": 7, "used_for_training": "no", "zdr": "available"}
    rec[item["id"]]["source_sha256"] = "0" * 64  # recorded from other bytes: not used
    assert dv.baseline_output(item, recorded=rec) is None


def test_every_recorded_reading_was_made_on_the_labelled_bytes():
    """Content addressing, checkable on a clone: each headline and reference reading records the sha256 of the page
    text Nemotron read, and it equals the sha256 of the capture the labels were written from."""
    corpus = {i["id"]: i for i in dv.load_corpus()}
    n = 0
    for p in dv.headline_runs() + dv.reference_runs():
        for c in json.loads(p.read_text())["calls"]:
            assert c["source_sha256"] == corpus[c["id"]]["source_sha256"], (p.name, c["id"])
            n += 1
    assert n == 150  # 39 v3fresh readings + 111 on the older items


def _git(*args) -> str | None:
    import subprocess
    try:
        return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=20).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


@pytest.mark.skipif(_git("rev-parse", "--is-shallow-repository") != "false", reason="needs a full git history")
def test_every_cited_preregistration_commit_exists_and_labels_precede_the_prompt():
    """The README and eval/datause/headline.json cite the commits that froze the labels and then the prompt; each id
    must resolve in this repository's history, and the labels commit must be an ancestor of the prompt commit."""
    pre = json.loads((ROOT / "eval" / "datause" / "headline.json").read_text())["preregistration"]
    labels, prompt = pre["labels_commit"], pre["prompt_v3_commit"]
    readme = (ROOT / "README.md").read_text()
    assert f"`{labels}`" in readme and f"`{prompt}`" in readme
    for c in (labels, prompt):
        assert _git("cat-file", "-t", c) == "commit", c
    import subprocess
    assert subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", labels, prompt]).returncode == 0
    touched = _git("show", "--name-only", "--format=", labels).split()
    assert "eval/datause/preregistration-v3.json" in touched
    assert "owin/datause/extract.py" in _git("show", "--name-only", "--format=", prompt).split()
    esc = json.loads((ROOT / "eval" / "datause" / "escalation-preregistration.json").read_text())
    assert esc["frozen"]["labels"]["labels_commit"] == labels
