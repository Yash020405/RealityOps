from copy import deepcopy

from env.core import RealityOpsEnv
from env.grader import grade
from env.models import Action
from env.worlds import WORLDS


def _prepare_multi_incident_env(seed: int = 21) -> RealityOpsEnv:
    env = RealityOpsEnv()
    env.reset(task_name="multi_incident", seed=seed)
    env.step(Action(type="check_logs"))
    env.step(Action(type="check_metrics"))
    env.step(Action(type="probe"))
    env.step(Action(type="update_belief", payload={"db_overload": 0.45, "network_partition": 0.45, "cache_bug": 0.1}))
    env.step(Action(type="update_belief", payload={"db_overload": 0.50, "network_partition": 0.40, "cache_bug": 0.1}))
    env.step(Action(type="update_belief", payload={"db_overload": 0.55, "network_partition": 0.40, "cache_bug": 0.05}))
    env.step(Action(type="safe_mitigation"))
    return env


def test_multi_incident_reset_creates_multiple_active_worlds() -> None:
    env = RealityOpsEnv()
    env.reset(task_name="multi_incident", seed=20)

    assert isinstance(env.state["active_world"], list)
    assert len(env.state["active_world"]) >= 2


def test_multi_incident_two_worlds_one_fixed_partial_credit() -> None:
    env = _prepare_multi_incident_env(seed=22)
    env.step(Action(type="commit_fix", payload={"fix": "increase_pool"}))

    result = env.score()
    assert 0.0 < result["components"]["correct_fix"] < 1.0


def test_multi_incident_two_worlds_neither_fixed() -> None:
    env = _prepare_multi_incident_env(seed=23)
    env.step(Action(type="commit_fix", payload={"fix": "refresh_token"}))

    result = env.score()
    assert result["components"]["correct_fix"] == 0.0


def test_multi_incident_wrong_world_chosen_scores_lower_than_correct_world_fix() -> None:
    wrong = _prepare_multi_incident_env(seed=24)
    wrong.step(Action(type="commit_fix", payload={"fix": "flush_cache"}))

    partial = _prepare_multi_incident_env(seed=24)
    partial.step(Action(type="commit_fix", payload={"fix": "increase_pool"}))

    assert wrong.score()["score"] < partial.score()["score"]


def test_multi_incident_partial_belief_update_does_not_complete_episode() -> None:
    env = RealityOpsEnv()
    env.reset(task_name="multi_incident", seed=25)

    env.step(Action(type="check_logs"))
    env.step(Action(type="check_metrics"))
    env.step(Action(type="probe"))
    env.step(Action(type="update_belief", payload={"db_overload": 0.7, "network_partition": 0.3}))
    env.step(Action(type="safe_mitigation"))
    attempt = env.step(Action(type="commit_fix", payload={"fix": "increase_pool"}))

    assert attempt["done"] is False
    assert attempt["info"]["requires_fix_confirmation"] is True


def test_multi_incident_fallback_to_single_world_mode() -> None:
    env = RealityOpsEnv()
    env.reset(task_name="multi_incident", seed=26)

    state = deepcopy(env.state)
    state["active_world"] = "db_overload"
    state["applied_fix"] = "increase_pool"

    result = grade(state, WORLDS)
    assert result["components"]["correct_fix"] == 1.0


def test_multi_incident_belief_alignment_handles_empty_world_list() -> None:
    env = RealityOpsEnv()
    env.reset(task_name="multi_incident", seed=27)

    state = deepcopy(env.state)
    state["active_world"] = []
    state["applied_fix"] = None

    result = grade(state, WORLDS)
    assert result["components"]["belief_alignment"] == 0.0
    assert 0.0 <= result["score"] <= 1.0


def test_multi_incident_two_fixes_progress_episode() -> None:
    env = _prepare_multi_incident_env(seed=28)
    first_fix = env.step(Action(type="commit_fix", payload={"fix": "increase_pool"}))
    second_fix = env.step(Action(type="commit_fix", payload={"fix": "reroute_traffic"}))

    assert first_fix["info"]["task"] == "multi_incident"
    assert second_fix["info"]["task"] == "multi_incident"
    assert second_fix["reward"] is not None
