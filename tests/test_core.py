import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from upwork_kit import flags, lint, outline, rates, roi, scoring
from upwork_kit.models import Job, parse_money, parse_range

EX = Path(__file__).resolve().parent.parent / "examples"
NOW = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)


def load(name):
    return json.loads((EX / name).read_text(encoding="utf-8"))


# ---------- models ----------
def test_parse_money_variants():
    assert parse_money("$1,000.00") == 1000.0
    assert parse_money(1200) == 1200.0
    assert parse_money("") is None
    assert parse_money(None) is None
    assert parse_money(True) is None


def test_parse_range_en_dash():
    assert parse_range("15.00–38.00/hr") == (15.0, 38.0)
    assert parse_range("40") == (40.0, 40.0)
    assert parse_range("nothing") == (None, None)


def test_official_shape_hourly_budget():
    j = Job.model_validate(load("job_official_mcp_shape.json"))
    assert j.job_type == "hourly"
    assert (j.hourly_min, j.hourly_max) == (25.0, 55.0)
    assert j.client.total_spent == 18400.0
    assert j.client.payment_verified is True
    assert j.description.startswith("We have 14 Zaps")


def test_missing_proposal_count_is_zero():
    assert Job.model_validate({"title": "x"}).proposal_count == 0


def test_hire_rate_derived_and_percent_normalised():
    j = Job.model_validate({"client": {"total_hires": 5, "total_posted_jobs": 10}})
    assert j.client.hire_rate == 0.5
    assert Job.model_validate({"client": {"hire_rate": "62%"}}).client.hire_rate == 0.62


def test_invalid_rating_rejected():
    with pytest.raises(Exception):
        Job.model_validate({"client": {"rating": 9}})


# ---------- scoring ----------
def test_good_job_bids():
    r = scoring.score_job(load("job_good.json"), now=NOW)
    assert r["verdict"] == "bid"
    assert r["score"] >= 65
    assert r["kill_gates"] == []


def test_bad_job_killed_with_reasons():
    r = scoring.score_job(load("job_bad.json"), now=NOW)
    gates = {g["gate"] for g in r["kill_gates"]}
    assert r["verdict"] == "kill"
    assert {"actual_price", "off_platform_payment", "payment_unverified", "low_hire_rate"} <= gates


def test_stale_posting_needs_liveness():
    d = load("job_good.json")
    d["created_date"] = "2026-10-01T00:00:00Z"
    assert scoring.score_job(d, now=NOW)["verdict"] == "kill"
    cfg = scoring.ScoreConfig(liveness_confirmed=True)
    assert "stale_unverified" not in {g["gate"] for g in scoring.score_job(d, cfg, NOW)["kill_gates"]}


def test_already_hired_kills():
    d = load("job_good.json")
    d["total_hired"] = 1
    assert "already_hired" in {g["gate"] for g in scoring.score_job(d, now=NOW)["kill_gates"]}


def test_excluded_country_configurable():
    cfg = scoring.ScoreConfig(excluded_countries=["united states"])
    r = scoring.score_job(load("job_good.json"), cfg, NOW)
    assert r["verdict"] == "kill"
    assert scoring.score_job(load("job_good.json"), now=NOW)["verdict"] == "bid"


def test_unknowns_are_reported_not_guessed():
    r = scoring.score_job({"title": "t", "description": "short"}, now=NOW)
    assert {"budget", "client.hire_rate", "payment_verified"} <= set(r["unknown"])
    assert r["verdict"] in {"skip", "maybe"}


def test_proposal_count_tiers():
    base = load("job_good.json")
    pts = {}
    for n in (3, 8, 12, 30):
        base["proposal_count"] = n
        row = [x for x in scoring.score_job(base, now=NOW)["breakdown"] if x["category"] == "proposal_count"][0]
        pts[n] = row["points"]
    assert pts == {3: 15, 8: 10, 12: 4, 30: 0}


def test_hire_rate_gate_needs_enough_posted_jobs():
    d = load("job_good.json")
    d["client"].update(total_hires=0, total_posted_jobs=2)
    d["client"].pop("hire_rate", None)
    assert "low_hire_rate" not in {g["gate"] for g in scoring.score_job(d, now=NOW)["kill_gates"]}


def test_hourly_low_avg_paid_gate():
    d = load("job_official_mcp_shape.json")
    d["client"]["avg_hourly_paid"] = 8
    assert "low_avg_hourly_paid" in {g["gate"] for g in scoring.score_job(d, now=NOW)["kill_gates"]}


def test_threshold_is_respected():
    d = load("job_good.json")
    assert scoring.score_job(d, scoring.ScoreConfig(bid_threshold=100), NOW)["verdict"] == "bid"
    assert scoring.score_job(d, scoring.ScoreConfig(bid_threshold=101 - 1), NOW)["score"] == 100


def test_render_text_mentions_verdict():
    assert scoring.render_text(scoring.score_job(load("job_bad.json"), now=NOW)).startswith("KILL")


# ---------- flags ----------
def test_actual_price_flag_is_kill():
    f = flags.scan("The budget is not a placeholder, it is the actual price.")
    assert any(x["id"] == "actual_price" and x["kill"] for x in f)


def test_clean_text_has_no_flags():
    assert flags.scan("We need an n8n workflow that syncs HubSpot to Slack. Budget is flexible.") == []


def test_off_platform_and_free_work_flags():
    ids = {x["id"] for x in flags.scan("Please do a free sample first, we pay via PayPal. WhatsApp me.")}
    assert {"free_work", "off_platform_payment", "off_platform_contact"} <= ids


def test_scope_budget_mismatch():
    text = "Build:\n" + "\n".join(f"- item {i}" for i in range(7))
    assert any(x["id"] == "budget_scope_mismatch" for x in flags.scan(text, fixed_budget=100))
    assert not any(x["id"] == "budget_scope_mismatch" for x in flags.scan(text, fixed_budget=5000))


def test_penalty_is_capped():
    big = flags.scan("actual price, outside upwork, free test, whatsapp, password, guaranteed profit")
    assert flags.penalty(big) == 20


# ---------- lint ----------
GOOD = (
    "Your CRM alerts and invoice drafts are the part of this job that decides whether a lead gets answered, "
    "so I would build the Slack alert first and wire error notifications in from day one. "
    "I have built n8n flows that connect a CRM to Slack and invoicing, with a failure branch that pings a channel "
    "instead of failing silently. For yours I would map the deal stages that should fire each alert, build and test the "
    "Slack and invoice steps against real records, then add monitoring so nothing breaks quietly. "
    "One question: does an invoice need approval before it is created, or can it go out as a draft automatically? "
    "I can start this week and share a short plan inside Upwork messages first, so you can confirm scope before anything is built."
)


def test_good_proposal_passes():
    r = lint.lint(GOOD, "n8n CRM Slack invoicing", "connect CRM to Slack and invoicing with n8n")
    assert r["ok"] is True
    assert 120 <= r["word_count"] <= 180
    assert r["questions"] == 1


def test_empty_and_short_are_errors():
    assert lint.lint("")["ok"] is False
    assert any(i["id"] == "word_count" and i["severity"] == "error" for i in lint.lint("Hi I can do it.")["issues"])


def test_contact_and_payment_detected():
    ids = {i["id"] for i in lint.lint("Mail me at jo@example.com, +1 415 555 0100, or pay by PayPal outside Upwork.")["issues"]}
    assert {"off_platform_email", "off_platform_phone", "off_platform_payment"} <= ids


def test_placeholder_detected():
    for t in ("Hello [Client Name], I can help.", "Hello {{name}}", "Hi <CLIENT NAME>", "lorem ipsum"):
        assert any(i["id"] == "placeholder" for i in lint.lint(t)["issues"]), t


def test_ai_tells_and_generic_opening():
    t = "Dear Sir, I hope this message finds you well. I will delve into your project and leverage cutting-edge tools."
    ids = {i["id"] for i in lint.lint(t)["issues"]}
    assert {"generic_opening", "ai_tell"} <= ids


def test_question_count_rules():
    assert any(i["id"] == "no_question" for i in lint.lint(GOOD.replace("?", "."))["issues"])
    many = GOOD + " Why? When? How? Who?"
    assert any(i["id"] == "too_many_questions" for i in lint.lint(many)["issues"])


def test_opening_mirror_warning():
    r = lint.lint("Greetings, I am a professional with years of general skills.", "n8n CRM Slack", "n8n workflow CRM Slack alerts")
    assert any(i["id"] == "opening_not_mirroring" for i in r["issues"])


def test_booking_link_is_warning_not_error():
    i = [x for x in lint.lint(GOOD + " Book at calendly.com/me")["issues"] if x["id"] == "booking_link"]
    assert i and i[0]["severity"] == "warn"


# ---------- outline ----------
JD = ("Start your proposal with the word PINEAPPLE. We need an n8n workflow connecting HubSpot to Slack.\n"
      "- New lead alert in Slack\n- Invoice draft on accepted quote\n- Error alerts\nWhat tools do you prefer for monitoring?")


def test_outline_picks_up_client_instruction_and_tools():
    o = outline.outline("n8n HubSpot Slack", JD, fixed_budget=900)
    assert any("PINEAPPLE" in x for x in o["client_instructions_to_follow"])
    assert {"n8n", "hubspot", "slack"} <= set(o["tools_mentioned"])
    assert len(o["deliverables"]) == 3
    assert o["client_questions_to_answer"] == ["What tools do you prefer for monitoring?"]


def test_outline_has_five_sections_and_fill_slot():
    o = outline.outline("t", JD)
    assert [s["section"] for s in o["sections"]] == ["hook", "proof", "plan", "question", "close"]
    assert "[FILL:" in o["skeleton"]


def test_outline_asks_budget_when_missing():
    o = outline.outline("t", "Need a developer to fix our site.")
    assert any(g["gap"] == "budget" for g in o["gaps_and_questions"])
    assert not any(g["gap"] == "budget" for g in outline.outline("t", "x", fixed_budget=500)["gaps_and_questions"])


def test_outline_skeleton_fails_lint_until_filled():
    o = outline.outline("t", JD)
    assert any(i["id"] == "placeholder" for i in lint.lint(o["skeleton"])["issues"])


# ---------- rates ----------
def test_upwork_documented_example_20_net_at_10pct():
    assert rates.net_to_gross(20, 10) == 22.22  # matches Upwork's help-article example


def test_second_documented_example():
    assert rates.net_to_gross(25, 10) == 27.78


def test_gross_to_net_roundtrip():
    assert rates.gross_to_net(100, 10) == 90.0
    assert rates.gross_to_net(100, 0) == 100.0
    assert rates.gross_to_net(100, 15) == 85.0


def test_fee_validation():
    with pytest.raises(ValueError):
        rates.net_to_gross(20, -1)
    with pytest.raises(ValueError):
        rates.net_to_gross(20, 31)


def test_fixed_mode_effective_hourly_includes_connects():
    r = rates.calculate("fixed", 1000, fee_percent=10, hours=20, connects_cost_usd=2.4)
    assert r["net_total"] == 900.0
    assert r["net_after_connects"] == 897.6
    assert r["effective_net_hourly"] == 44.88


def test_projection():
    r = rates.calculate("gross_to_net", 50, 10, hours_per_week=20, weeks=4)
    assert r["net_hourly"] == 45.0 and r["projected_net_total"] == 3600.0


def test_bad_mode_and_negative_amount():
    with pytest.raises(ValueError):
        rates.calculate("nope", 1)
    with pytest.raises(ValueError):
        rates.calculate("fixed", -5)


# ---------- roi ----------
def test_roi_good_bid():
    r = roi.connects_roi(16, 1800, proposal_count=4, quality_score=90)
    assert r["recommendation"] == "bid"
    assert r["connects_cost_usd"] == 2.4
    assert r["win_probability_source"].startswith("heuristic")


def test_roi_skip_when_tiny_value_and_crowded():
    r = roi.connects_roi(16, 10, proposal_count=40, quality_score=20)
    assert r["recommendation"] == "skip"
    assert r["expected_value_usd"] < 0


def test_roi_own_probability_overrides_prior():
    r = roi.connects_roi(10, 500, win_probability=0.5)
    assert r["win_probability"] == 0.5 and r["win_probability_source"] == "supplied win_probability"


def test_roi_break_even():
    r = roi.connects_roi(10, 1000, win_probability=0.1, fee_percent=0)
    assert r["break_even_win_probability"] == round(1.5 / 1000, 4)


def test_roi_validation():
    with pytest.raises(ValueError):
        roi.connects_roi(10, 100, win_probability=1.5)
    with pytest.raises(ValueError):
        roi.connects_roi(-1, 100)


def test_prior_decreases_with_crowd():
    assert roi.prior_win_probability(2) > roi.prior_win_probability(20)
