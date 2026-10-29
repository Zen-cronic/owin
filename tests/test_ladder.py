"""The Nemotron ladder and the pre-registered escalation: recomputed keyless from recorded runs; the rule can only
answer a cell Super sent to a person, only with a value Super's readings gave, and never re-opens a Super answer."""
import json

from owin.datause import evaluate as dv, ladder, selective

PRE = json.loads(ladder.PREREG.read_text())


def _fake_run(tmp_path, name, mutate):
    """A copy of the headline Super run with each call's terms passed through `mutate(item_id, run, terms)`."""
    d = json.loads(dv.headline_runs()[0].read_text())
    for c in d["calls"]:
        if c.get("terms"):
            c["terms"] = mutate(c["id"], c["run"], dict(c["terms"]))
    p = tmp_path / f"{name}.json"
    p.write_text(json.dumps(d))
    return p


def _confirm_cells():
    rep = selective.evaluate(dv.headline_runs(), split="v3fresh")
    return {(c["item"], c["field"]): c for c in rep["confirm_cells"]}


def test_preregistration_fixes_the_rule_and_bar_before_the_runs():
    assert PRE["split"] == "v3fresh" and set(PRE["arms"]) == {"super", "nano", "lightning", "ultra"}
    assert "never re-opened" in PRE["escalation_rule"] and "strictly fewer" in PRE["adoption_bar"]


def test_an_arbiter_that_agrees_with_super_answers_nothing_new_on_its_own(tmp_path):
    same = _fake_run(tmp_path, "same", lambda i, k, t: t)  # Ultra = a replay of Super's own readings
    e = ladder.escalate(dv.headline_runs()[0], same)
    assert e["sent_to_person"] == 6 and e["resolved_by_ultra"] == "0/0"  # Super's splits stay split


def test_unanimous_arbiter_on_a_super_value_answers_the_cell(tmp_path):
    gold = {i["id"]: i["gold"] for i in dv.load_corpus()}
    conf = _confirm_cells()
    truth = _fake_run(tmp_path, "truth", lambda i, k, t: {**t, **{f: gold[i][f] for (ii, f) in conf if ii == i}})
    e = ladder.escalate(dv.headline_runs()[0], truth)
    # Cells it answers are answered right; the verbatim gate still applies to the arbiter's readings, so a value
    # whose sentence is not on the page is withheld and that cell stays with the person.
    right, n = map(int, e["resolved_by_ultra"].split("/"))
    assert right == n >= 4 and e["sent_to_person"] == 6 - n and not e["confident_misses"][1:]


def test_arbiter_never_reopens_a_super_answer_or_invents_a_value(tmp_path):
    def wrong(i, k, t):  # Ultra unanimously says something no Super reading said, on every field
        return {**t, "retention_days": 12345, "used_for_training": "yes", "zdr": "not_available"}
    e = ladder.escalate(dv.headline_runs()[0], _fake_run(tmp_path, "wrong", wrong))
    sup = selective.evaluate(dv.headline_runs(), split="v3fresh")
    assert e["auto_answered"] == sup["auto_answered"] and e["auto_correct"] == sup["auto_correct"]
    assert e["sent_to_person"] == 6 and e["resolved_by_ultra"] == "0/0"


def test_an_arbiter_with_fewer_than_two_good_readings_abstains(tmp_path):
    d = json.loads(dv.headline_runs()[0].read_text())
    for c in d["calls"]:
        if c["run"] > 0:
            c["terms"], c["error"] = None, "HTTP 529"
    p = tmp_path / "errored.json"
    p.write_text(json.dumps(d))
    assert ladder.escalate(dv.headline_runs()[0], p)["sent_to_person"] == 6


def test_ladder_report_recomputes_keyless_with_the_super_arm():
    rep = ladder.report()
    s = rep["arms"]["super"]
    assert (s["auto_answered"], s["auto_correct"], s["sent_to_confirm"]) == ("27/33", "26/27", 6)


def _ts(s: str):
    from datetime import datetime
    s = s if s[-3] == ":" or s.endswith("Z") else s[:-2] + ":" + s[-2:]
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def test_every_arm_ran_after_the_preregistration_was_committed():
    import subprocess
    rec = json.loads(ladder.LADDER.read_text())
    assert set(rec["arms"]) == {"nano", "lightning", "ultra"}  # one scored run per arm
    written = _ts(PRE["written_at"])
    git = subprocess.run(["git", "-C", str(ladder.ROOT), "log", "--diff-filter=A", "--format=%cI", "--",
                          "eval/datause/escalation-preregistration.json"], capture_output=True, text=True)
    committed = [_ts(x) for x in git.stdout.split()] if git.returncode == 0 and git.stdout.strip() else []
    for name, f in rec["arms"].items():
        run_at = _ts(json.loads((ladder.ROOT / f).read_text())["run_at"])
        assert run_at > written, name
        if committed:  # with history: the pre-registration commit is older than every arm
            assert run_at > committed[-1], name


def test_ladder_numbers_recompute_from_the_recorded_arms():
    rep = ladder.report()
    e = rep["escalation"]
    n, k = e["resolved_by_ultra"].split("/")[::-1]
    assert e["sent_to_person"] == 6 - int(n) and e["adopted"] is (e["sent_to_person"] < 6 and len(e["confident_misses"]) <= 1)
    assert all(c["by"] == "ultra" and c["super_split"] for c in e["ultra_cells"])
