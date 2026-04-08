from copy import deepcopy

from env.grader import grade
from env.worlds import WORLDS


BASE_STATE = {
    "task_name": "ambiguous_root",
    "active_world": "db_overload",
    "beliefs": {"db_overload": 0.7, "cache_bug": 0.2, "auth_expiry": 0.1},
    "applied_fix": "increase_pool",
    "requires_fix_confirmation": False,
    "mitigation_applied": False,
    "mitigation_step": None,
    "fix_step": 3,
    "risky_used": False,
    "repeat_actions": 0,
    "premature_fix_count": 0,
    "invalid_fix_count": 0,
    "belief_update_count": 1,
    "wait_count": 0,
    "investigations": {
        "probe": True,
        "check_logs": True,
        "check_metrics": True,
    },
    "action_history": [
        {"step": 1, "type": "check_logs", "payload": {}},
        {"step": 2, "type": "check_metrics", "payload": {}},
        {"step": 3, "type": "commit_fix", "payload": {"fix": "increase_pool"}},
    ],
    "reward_history": [0.62, 0.71, 0.88],
    "steps": 3,
    "done": False,
    "revenue_loss": 12000.0,
    "episode_score": 0.0,
    "seed": 42,
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


def _state_for(task_name: str) -> dict:
    state = deepcopy(BASE_STATE)
    state["task_name"] = task_name

    if task_name == "false_alarm":
        state["active_world"] = "no_incident"
        state["applied_fix"] = "no_fix"
    elif task_name == "ambiguous_root":
        state["active_world"] = "db_overload"
        state["applied_fix"] = "increase_pool"
    elif task_name == "revenue_tradeoff":
        state["active_world"] = "network_partition"
        state["applied_fix"] = "reroute_traffic"
        state["mitigation_step"] = 2
        state["task_spec"]["require_mitigation_before_fix"] = True
    elif task_name == "cascading_failure":
        state["active_world"] = "auth_expiry"
        state["applied_fix"] = "refresh_token"
        state["action_history"] = [
            {"step": 1, "type": "check_logs", "payload": {}},
            {"step": 2, "type": "update_belief", "payload": {}},
            {"step": 3, "type": "update_belief", "payload": {}},
            {"step": 4, "type": "commit_fix", "payload": {"fix": "refresh_token"}},
        ]
    elif task_name == "multi_incident":
        state["active_world"] = ["db_overload", "network_partition"]
        state["beliefs"] = {
            "db_overload": 0.5,
            "network_partition": 0.4,
            "cache_bug": 0.1,
            "auth_expiry": 0.0,
        }
        state["applied_fix"] = "increase_pool"
        state["task_spec"]["max_steps"] = 12
        state["task_spec"]["revenue_loss_per_step"] = 15000
    elif task_name == "security_breach":
        state["active_world"] = "security_breach"
        state["beliefs"] = {"security_breach": 0.7, "no_incident": 0.2, "auth_expiry": 0.1}
        state["applied_fix"] = "block_ip"
        state["mitigation_step"] = 1
    elif task_name == "resource_exhaustion":
        state["active_world"] = "resource_exhaustion"
        state["beliefs"] = {"resource_exhaustion": 0.8, "db_overload": 0.1, "cache_bug": 0.1}
        state["applied_fix"] = "scale_up"

    return state


def test_false_alarm_weights_sum_to_one() -> None:
    assert abs((0.40 + 0.25 + 0.20 + 0.10 + 0.05) - 1.0) < 1e-12


def test_ambiguous_root_weights_sum_to_one() -> None:
    assert abs((0.48 + 0.20 + 0.17 + 0.10 + 0.05) - 1.0) < 1e-12


def test_revenue_tradeoff_weights_sum_to_one() -> None:
    assert abs((0.42 + 0.25 + 0.20 + 0.08 + 0.05) - 1.0) < 1e-12


def test_cascading_failure_weights_sum_to_one() -> None:
    assert abs((0.37 + 0.25 + 0.20 + 0.13 + 0.05) - 1.0) < 1e-12


def test_multi_incident_weights_sum_to_one() -> None:
    assert abs((0.40 + 0.20 + 0.15 + 0.15 + 0.05 + 0.05) - 1.0) < 1e-12


def test_security_breach_weights_sum_to_one() -> None:
    assert abs((0.42 + 0.23 + 0.15 + 0.10 + 0.05 + 0.05) - 1.0) < 1e-12


def test_resource_exhaustion_weights_sum_to_one() -> None:
    assert abs((0.50 + 0.20 + 0.15 + 0.10 + 0.05) - 1.0) < 1e-12


def test_score_always_within_zero_one_for_all_tasks() -> None:
    for task in [
        "false_alarm",
        "ambiguous_root",
        "revenue_tradeoff",
        "cascading_failure",
        "multi_incident",
        "security_breach",
        "resource_exhaustion",
    ]:
        result = grade(_state_for(task), WORLDS)
        assert 0.0 <= result["score"] <= 1.0


def test_security_breach_penalizes_repeated_actions() -> None:
    disciplined = _state_for("security_breach")
    noisy = _state_for("security_breach")
    noisy["repeat_actions"] = 4
    noisy["wait_count"] = 7

    disciplined_score = grade(disciplined, WORLDS)["score"]
    noisy_score = grade(noisy, WORLDS)["score"]

    assert noisy_score < disciplined_score


def test_score_precision_is_stable_under_small_floats() -> None:
    state = _state_for("ambiguous_root")
    state["revenue_loss"] = 12345.678901
    state["beliefs"] = {
        "db_overload": 0.3333333333,
        "cache_bug": 0.3333333333,
        "auth_expiry": 0.3333333334,
    }

    result = grade(state, WORLDS)
    assert 0.0 <= result["score"] <= 1.0
    assert all(isinstance(v, float) for v in result["components"].values())
