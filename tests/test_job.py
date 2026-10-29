"""`owin job daily`: the unattended chain (sweep, refresh, Nemotron re-reading, registry export) into a state dir.
The Nemotron step is mocked here; an errored reading abstains, and a step that fails is recorded, never hidden."""
import json
from dataclasses import replace

import pytest

from owin import cli, config, tokenfactory as tf
from owin.datause import pack, registry
from owin.extract import Extraction

FEATS = sorted({e["feature"] for e in pack.load_demo()["endpoints"]})


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("OWIN_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setenv("OWIN_ENV_FILE", str(tmp_path / "no.env"))
    monkeypatch.setattr(tf, "LEDGER", tmp_path / "usage.jsonl")
    # Stand-in Tavily captures: the committed quotes of each page, so the verbatim gate and the evidence index work.
    raw = tmp_path / "tavily"
    raw.mkdir()
    from owin.datause import evidence, observations
    for page in registry.load_catalog()["pages"]:
        raw.joinpath(f"{page}.md").write_text("\n\n".join(observations.page_quotes(page).values()) + "\n")
    monkeypatch.setattr(registry, "TAVILY_RAW", raw)
    monkeypatch.setattr(evidence, "TAVILY_RAW", raw)
    evidence._index.cache_clear()
    yield
    evidence._index.cache_clear()


def _fake_reader(fail: dict[str, int]):
    """Nemotron stand-in: returns the committed registry terms for a feature; the first `fail[feature]` readings error."""
    seen = {}
    reg = registry.load()

    def extract(item_id, vendor, feature, source, *, model=tf.SUPER, purpose="datause"):
        k = seen.get(item_id, 0)
        seen[item_id] = k + 1
        base = Extraction(item_id, model, "sha", "whole", len(source), 0.1, 10, 10, 0.0001, "stop", None, None, "")
        if k < fail.get(item_id, 0):
            return replace(base, error="HTTP 503", finish_reason=None)
        return replace(base, terms=reg[item_id]["terms"])
    return extract


def _run(monkeypatch, capsys, fail: dict[str, int], key: bool = True) -> dict:
    if key:
        monkeypatch.setenv("TOKEN_FACTORY_API_KEY", "tf-test")
    monkeypatch.setattr(registry, "extract", _fake_reader(fail))
    assert cli.main(["job", "daily", "--no-fetch"]) == 0
    return json.loads(capsys.readouterr().out)


def test_job_reads_with_nemotron_and_exports_into_the_state_dir(monkeypatch, capsys, tmp_path):
    out = _run(monkeypatch, capsys, fail={})
    r = out["readings"]
    assert r["calls"] == 3 * len(FEATS) and r["errored_abstained"] == 0 and r["prompt_version"] == "v3"
    assert set(r["features"]) == set(FEATS) and all(v["left_to_a_person"] == [] for v in r["features"].values())
    sd = tmp_path / "state"
    assert (sd / "data/datause/registry.json").exists() and (sd / "data/datause/evidence.json").exists()
    assert sd.joinpath("eval/datause/registry-runs").glob("*.json") and json.loads((tmp_path / "state" / out["record"].split("state/")[1]).read_text())["job"] == "daily"
    assert out["sweep"]["vendors"] == 29 and out["pack_refresh"]["tavily_calls"] == 0
    # The endpoint reads the refreshed registry from the state dir; the committed file is untouched.
    assert config.read_path("data/datause/registry.json") == sd / "data/datause/registry.json"
    assert {a["id"]: a["badge"] for a in pack.build()["answers"]}["Q03"] == "not_true"


def test_an_errored_reading_abstains_and_two_errors_send_the_field_to_a_person(monkeypatch, capsys):
    out = _run(monkeypatch, capsys, fail={"anthropic-mcp-connector": 1, "openai-embeddings": 2})
    f = out["readings"]["features"]
    assert out["readings"]["errored_abstained"] == 3
    # One of three errored: the other two agree, so every field is still answered on its own.
    assert f["anthropic-mcp-connector"]["errored_abstained"] == 1 and f["anthropic-mcp-connector"]["runs_agreeing"] == "2/3"
    assert f["anthropic-mcp-connector"]["left_to_a_person"] == []
    # Two of three errored: one reading is not enough to answer; the fields wait for a person.
    assert f["openai-embeddings"]["errored_abstained"] == 2 and f["openai-embeddings"]["left_to_a_person"] == sorted(registry.DECIDING_FIELDS)
    reg = registry.load()
    assert reg["openai-embeddings"]["field_agreement"]["zdr"] == {**reg["openai-embeddings"]["field_agreement"]["zdr"], "state": "confirm", "readings_failed": 2}


def test_job_without_a_token_factory_key_skips_the_reading_and_says_so(monkeypatch, capsys):
    out = _run(monkeypatch, capsys, fail={}, key=False)
    assert "TOKEN_FACTORY_API_KEY" in out["readings"]["skipped"] and out["sweep"]["vendors"] == 29


def test_job_reading_failure_is_recorded_not_raised(monkeypatch, capsys):
    monkeypatch.setenv("TOKEN_FACTORY_API_KEY", "tf-test")
    monkeypatch.setattr(registry, "extract_live", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert cli.main(["job", "daily", "--no-fetch"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["readings"]["error"].startswith("RuntimeError: boom")
