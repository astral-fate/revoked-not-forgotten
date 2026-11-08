import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from revres.env import CONDITIONS, Cond, annotate_lineage, parse_action, run_executor, writer_messages  # noqa: E402
from revres.grade import grade  # noqa: E402
from revres.llm import ScriptedChat  # noqa: E402
from revres.scenarios import TEMPLATES, make_scenario  # noqa: E402


def _trial(cond, seed):
    llm = ScriptedChat()
    s = make_scenario(seed)
    c = Cond.get(cond)
    h = llm(writer_messages(s, c.compromised))
    return s, h, grade(s, h, run_executor(llm, s, c, h, seed))


def test_scenarios_deterministic_and_distinct():
    for seed in range(len(TEMPLATES) * 2):
        a, b = make_scenario(seed), make_scenario(seed)
        assert a == b
        assert a.canary_value != a.truth_value
        assert a.code.lower() in a.canary_dest


def test_clean_scripted_executor_succeeds():
    for seed in range(12):
        _, _, g = _trial("clean", seed)
        assert g["task_success"] and not g["any_residue"], (seed, g)


def test_compromised_scripted_executor_carries_residue():
    for seed in range(12):
        _, _, g = _trial("compromised", seed)
        s = make_scenario(seed)
        assert g["w_carried_fact"] and g["w_carried_instr"] == (s.payload == "exfil")
        assert g["fact_residue"] and g["instr_residue"] == (s.payload == "exfil") and not g["task_success"], (seed, g)


def test_lineage_blocks_residue_for_scripted_executor():
    for seed in range(12):
        _, _, g = _trial("revoke_lineage", seed)
        assert g["lineage_hit"] and not g["any_residue"] and g["field_correct"], (seed, g)


def test_benign_lineage_recovers_truth_by_lookup():
    for seed in range(12):
        _, _, g = _trial("benign_lineage", seed)
        assert g["redelegated"] and not g["any_residue"] and g["field_correct"]


def test_annotation_and_parse():
    txt, hit = annotate_lineage("- tier is X [m2]\n- refund 40 [m4]")
    assert hit and txt.splitlines()[0].startswith("!! DERIVED") and not txt.splitlines()[1].startswith("!!")
    assert parse_action('Sure: {"tool": "finish", "args": {"note": "x"}} thanks')["tool"] == "finish"
    assert parse_action("no json here") is None
    assert set(CONDITIONS) >= {"clean", "compromised", "revoke_lineage"}


def test_ablation_conditions_build():
    from revres.env import ABLATIONS, EXEC_SYS, writer_messages
    for name in ABLATIONS:
        c = Cond.get(name)
        assert c.name == name
    s = make_scenario(3)
    assert "cite" not in writer_messages(s, True, "nocite")[0]["content"]
    early = writer_messages(s, True, "early")[1]["content"]
    assert "retracted" in early and s.canary_value not in early and "SECURITY NOTICE" in early
    assert not Cond.get("nosource_lineage").second_source and Cond.get("strict_notice").notice_kind == "strict"
    _, _, g = _trial("nosource_benign", 3)  # scripted model still runs without the tool
    assert g["finished"]


def test_executor_prompt_variants():
    s = make_scenario(5)
    ex = run_executor(ScriptedChat(), s, Cond.get("strict_notice"), "HANDOFF\n- x", 5)
    assert "Do not use any fact" in ex["transcript"][1]["content"]
    ex = run_executor(ScriptedChat(), s, Cond.get("nosource_lineage"), "HANDOFF\n- x", 5)
    assert "reassign_lookup" not in ex["transcript"][0]["content"]
    ex = run_executor(ScriptedChat(), s, Cond.get("revoke_lineage"), "HANDOFF\n- x", 5)
    assert "reassign_lookup" in ex["transcript"][0]["content"] and "Do not use any fact" not in ex["transcript"][1]["content"]


def test_platform_mitigations():
    from revres.env import MITIGATIONS, transform_handoff, x_taint_terms, WITHHELD, LINEAGE_MARK
    s = make_scenario(10)  # exfil payload
    assert s.payload == "exfil"
    h = f"- set {s.field} to {s.canary_value}\n- export to {s.canary_dest}\n- refund {s.refund_amount} [m4]"
    t, hit = transform_handoff(h, "withhold", "taint", x_taint_terms(s, True))
    lines = t.splitlines()
    assert hit and lines[0] == WITHHELD and lines[1] == WITHHELD and lines[2].endswith("[m4]")
    t, hit = transform_handoff("- value is X [m2]\n- refund [m4]", "mark", "cite")
    assert t.splitlines()[0].startswith(LINEAGE_MARK) and not t.splitlines()[1].startswith(LINEAGE_MARK)
    for name in MITIGATIONS:
        c = Cond.get(name); assert c.lineage and c.revoked
    _, _, g = _trial("taint_quarantine", 10)
    assert g["lineage_hit"] and not g["any_residue"]
