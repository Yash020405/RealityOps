from copy import deepcopy

from pydantic import ValidationError

from env.grader import grade
from env.models import Action
from env.worlds import WORLDS


def _edge_state() -> dict:
    return {
        "task_name": "ambiguous_root",
        "active_world": "db_overload",
        "beliefs": {"db_overload": 1.0, "cache_bug": 0.0, "auth_expiry": 0.0},
        "applied_fix": "increase_pool",
        "requires_fix_confirmation": False,
        "mitigation_applied": False,
        "mitigation_step": None,
        "fix_step": 1,
        "risky_used": False,
        "repeat_actions": 0,
        "premature_fix_count": 0,
        "invalid_fix_count": 0,
        "belief_update_count": 1,
        "wait_count": 0,
        "investigations": {"probe": True, "check_logs": True, "check_metrics": True},
        "action_history": [{"step": 1, "type": "commit_fix", "payload": {"fix": "increase_pool"}}],
        "reward_history": [0.9],
        "steps": 1,
        "done": False,
        "revenue_loss": 0.0,
        "episode_score": 0.0,
        "seed": 100,
        "team_queries": 0,
        "belief_history": [],
        "market_hours": True,
        "task_spec": {
            "max_steps": 8,
            "revenue_loss_per_step": 5000,
            "required_evidence": 2,
            "required_belief_updates": 1,
            "require_mitigation_before_fix": False,
        },
    }


def test_empty_investigations_is_handled() -> None:
    state = _edge_state()
    state["investigations"] = {}

    result = grade(state, WORLDS)
    assert result["components"]["evidence"] == 0.0
    assert 0.0 <= result["score"] <= 1.0


def test_zero_max_steps_is_handled() -> None:
    state = _edge_state()
    state["task_spec"]["max_steps"] = 0

    result = grade(state, WORLDS)
    assert 0.0 <= result["score"] <= 1.0


def test_negative_revenue_loss_does_not_break_score_bounds() -> None:
    state = _edge_state()
    state["revenue_loss"] = -99999

    result = grade(state, WORLDS)
    assert 0.0 <= result["score"] <= 1.0


def test_high_penalties_still_clamp_score_to_zero_one() -> None:
    state = _edge_state()
    state["repeat_actions"] = 999
    state["premature_fix_count"] = 999
    state["invalid_fix_count"] = 999
    state["wait_count"] = 999

    result = grade(state, WORLDS)
    assert 0.0 <= result["score"] <= 1.0


def test_unsupported_task_returns_zero_score_payload() -> None:
    state = _edge_state()
    state["task_name"] = "unsupported_task"

    result = grade(state, WORLDS)
    assert result["score"] == 0.0
    assert "unsupported_task" in result["components"]


def test_action_model_rejects_invalid_literal_type() -> None:
    try:
        Action(type="not_valid")
        assert False, "ValidationError expected for invalid action literal"
    except ValidationError:
        assert True


def test_action_model_accepts_valid_fix_payload() -> None:
    action = Action(type="commit_fix", payload={"fix": "reroute_traffic"})
    assert action.type == "commit_fix"
    assert action.payload == {"fix": "reroute_traffic"}


def test_multi_incident_empty_active_world_list_is_handled() -> None:
    state = _edge_state()
    state["task_name"] = "multi_incident"
    state["active_world"] = []
    state["beliefs"] = {"db_overload": 0.5, "network_partition": 0.5}

    result = grade(state, WORLDS)
    assert 0.0 <= result["score"] <= 1.0


def test_score_components_are_rounded_to_four_decimals() -> None:
    state = _edge_state()
    state["revenue_loss"] = 12345.678901

    result = grade(state, WORLDS)
    for value in result["components"].values():
        text = str(value)
        if "." in text:
            assert len(text.split(".")[1]) <= 4


def test_grade_is_deterministic_for_same_state() -> None:
    state = _edge_state()
    first = grade(deepcopy(state), WORLDS)
    second = grade(deepcopy(state), WORLDS)
    assert first == second
