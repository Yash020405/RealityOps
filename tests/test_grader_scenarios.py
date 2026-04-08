from copy import deepcopy

from env.grader import grade
from env.worlds import WORLDS


def _base_state(task_name: str, active_world, applied_fix):
    return {
        "task_name": task_name,
        "active_world": active_world,
        "beliefs": {
            "db_overload": 0.4,
            "cache_bug": 0.2,
            "auth_expiry": 0.2,
            "network_partition": 0.15,
            "no_incident": 0.05,
            "security_breach": 0.0,
            "resource_exhaustion": 0.0,
        },
        "applied_fix": applied_fix,
        "requires_fix_confirmation": False,
        "mitigation_applied": False,
        "mitigation_step": None,
        "fix_step": 4,
        "risky_used": False,
        "repeat_actions": 0,
        "premature_fix_count": 0,
        "invalid_fix_count": 0,
        "belief_update_count": 1,
        "wait_count": 0,
        "investigations": {"probe": True, "check_logs": True, "check_metrics": True},
        "action_history": [
            {"step": 1, "type": "check_logs", "payload": {}},
            {"step": 2, "type": "check_metrics", "payload": {}},
            {"step": 3, "type": "update_belief", "payload": {}},
            {"step": 4, "type": "commit_fix", "payload": {"fix": applied_fix}},
        ],
        "reward_history": [0.4, 0.45, 0.52, 0.87],
        "steps": 4,
        "done": False,
        "revenue_loss": 12000.0,
        "episode_score": 0.0,
        "seed": 1,
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


def test_false_alarm_wait_like_behavior_scores_higher_than_unnecessary_fix() -> None:
    safe = _base_state("false_alarm", "no_incident", "no_fix")
    unsafe = _base_state("false_alarm", "no_incident", "increase_pool")

    assert grade(safe, WORLDS)["score"] > grade(unsafe, WORLDS)["score"]


def test_ambiguous_root_correct_fix_scores_higher_than_wrong_fix() -> None:
    correct = _base_state("ambiguous_root", "db_overload", "increase_pool")
    wrong = _base_state("ambiguous_root", "db_overload", "flush_cache")

    assert grade(correct, WORLDS)["score"] > grade(wrong, WORLDS)["score"]


def test_revenue_tradeoff_mitigation_before_fix_scores_higher() -> None:
    with_mitigation = _base_state("revenue_tradeoff", "network_partition", "reroute_traffic")
    with_mitigation["task_spec"]["require_mitigation_before_fix"] = True
    with_mitigation["mitigation_step"] = 2

    without_mitigation = deepcopy(with_mitigation)
    without_mitigation["mitigation_step"] = None

    assert grade(with_mitigation, WORLDS)["score"] > grade(without_mitigation, WORLDS)["score"]


def test_cascading_failure_two_belief_updates_score_better_than_one() -> None:
    one_update = _base_state("cascading_failure", "auth_expiry", "refresh_token")
    one_update["action_history"] = [
        {"step": 1, "type": "check_logs", "payload": {}},
        {"step": 2, "type": "update_belief", "payload": {}},
        {"step": 3, "type": "commit_fix", "payload": {"fix": "refresh_token"}},
    ]

    two_updates = deepcopy(one_update)
    two_updates["action_history"] = [
        {"step": 1, "type": "check_logs", "payload": {}},
        {"step": 2, "type": "update_belief", "payload": {}},
        {"step": 3, "type": "update_belief", "payload": {}},
        {"step": 4, "type": "commit_fix", "payload": {"fix": "refresh_token"}},
    ]

    assert grade(two_updates, WORLDS)["score"] > grade(one_update, WORLDS)["score"]


def test_multi_incident_one_of_two_fixes_gives_partial_credit() -> None:
    state = _base_state("multi_incident", ["db_overload", "network_partition"], "increase_pool")
    result = grade(state, WORLDS)

    assert result["components"]["correct_fix"] == 0.5


def test_multi_incident_both_wrong_results_in_zero_correct_fix() -> None:
    state = _base_state("multi_incident", ["db_overload", "network_partition"], "refresh_token")
    result = grade(state, WORLDS)

    assert result["components"]["correct_fix"] == 0.0


def test_security_breach_risky_action_penalty_reduces_score() -> None:
    safe = _base_state("security_breach", "security_breach", "block_ip")
    risky = deepcopy(safe)
    risky["risky_used"] = True

    assert grade(safe, WORLDS)["score"] > grade(risky, WORLDS)["score"]


def test_resource_exhaustion_correct_fix_scores_higher_than_wrong_fix() -> None:
    correct = _base_state("resource_exhaustion", "resource_exhaustion", "scale_up")
    wrong = _base_state("resource_exhaustion", "resource_exhaustion", "increase_pool")

    assert grade(correct, WORLDS)["score"] > grade(wrong, WORLDS)["score"]


def test_repeat_action_penalty_behaves_linearly_with_cap() -> None:
    low_repeat = _base_state("ambiguous_root", "db_overload", "increase_pool")
    high_repeat = deepcopy(low_repeat)

    low_repeat["repeat_actions"] = 1
    high_repeat["repeat_actions"] = 2

    low_anti = grade(low_repeat, WORLDS)["components"]["anti_gaming"]
    high_anti = grade(high_repeat, WORLDS)["components"]["anti_gaming"]

    # One extra repeat should drop anti-gaming by 0.05 until cap is reached.
    assert abs((low_anti - high_anti) - 0.05) < 1e-6
