from env.core import RealityOpsEnv
from env.models import Action


def test_cascading_failure_requires_two_belief_updates_gate() -> None:
    env = RealityOpsEnv()
    env.reset(task_name="cascading_failure", seed=7)

    env.step(Action(type="check_logs"))
    env.step(Action(type="check_metrics"))
    env.step(Action(type="probe"))
    env.step(Action(type="update_belief", payload={"auth_expiry": 0.8, "db_overload": 0.2}))

    attempt = env.step(Action(type="commit_fix", payload={"fix": "refresh_token"}))
    assert attempt["done"] is False
    assert attempt["info"]["requires_fix_confirmation"] is True


def test_cascading_failure_passes_after_second_belief_update() -> None:
    env = RealityOpsEnv()
    env.reset(task_name="cascading_failure", seed=8)

    env.step(Action(type="check_logs"))
    env.step(Action(type="check_metrics"))
    env.step(Action(type="probe"))
    env.step(Action(type="update_belief", payload={"auth_expiry": 0.7, "db_overload": 0.3}))
    env.step(Action(type="update_belief", payload={"auth_expiry": 0.9, "db_overload": 0.1}))

    attempt = env.step(Action(type="commit_fix", payload={"fix": "refresh_token"}))
    assert attempt["done"] is True


def test_revenue_tradeoff_requires_mitigation_before_fix_gate() -> None:
    env = RealityOpsEnv()
    env.reset(task_name="revenue_tradeoff", seed=9)

    env.step(Action(type="check_logs"))
    env.step(Action(type="check_metrics"))
    env.step(Action(type="probe"))
    env.step(Action(type="update_belief", payload={"network_partition": 0.8, "db_overload": 0.2}))

    attempt = env.step(Action(type="commit_fix", payload={"fix": "reroute_traffic"}))
    assert attempt["done"] is False
    # This path fails the mitigation gate but does not set a premature-fix confirmation flag.
    assert attempt["info"]["requires_fix_confirmation"] is False


def test_revenue_tradeoff_completes_when_mitigation_then_fix() -> None:
    env = RealityOpsEnv()
    env.reset(task_name="revenue_tradeoff", seed=10)

    env.step(Action(type="check_logs"))
    env.step(Action(type="check_metrics"))
    env.step(Action(type="probe"))
    env.step(Action(type="update_belief", payload={"network_partition": 0.75, "db_overload": 0.25}))
    env.step(Action(type="safe_mitigation"))

    attempt = env.step(Action(type="commit_fix", payload={"fix": "reroute_traffic"}))
    assert attempt["done"] is True


def test_security_breach_requires_mitigation_before_fix() -> None:
    env = RealityOpsEnv()
    env.reset(task_name="security_breach", seed=11)

    env.step(Action(type="check_logs"))
    env.step(Action(type="check_metrics"))
    env.step(Action(type="update_belief", payload={"security_breach": 0.85, "no_incident": 0.15}))
    attempt = env.step(Action(type="commit_fix", payload={"fix": "block_ip"}))

    assert attempt["done"] is False
    assert attempt["info"]["requires_fix_confirmation"] is False


def test_security_breach_completes_after_mitigation_confirmation() -> None:
    env = RealityOpsEnv()
    env.reset(task_name="security_breach", seed=12)

    env.step(Action(type="check_logs"))
    env.step(Action(type="check_metrics"))
    env.step(Action(type="update_belief", payload={"security_breach": 0.8, "auth_expiry": 0.2}))
    env.step(Action(type="safe_mitigation"))
    result = env.step(Action(type="commit_fix", payload={"fix": "block_ip"}))

    assert result["done"] is True


def test_requires_fix_confirmation_clears_after_gates_met() -> None:
    env = RealityOpsEnv()
    env.reset(task_name="revenue_tradeoff", seed=13)

    premature = env.step(Action(type="commit_fix", payload={"fix": "reroute_traffic"}))
    assert premature["info"]["requires_fix_confirmation"] is True

    env.step(Action(type="check_logs"))
    env.step(Action(type="check_metrics"))
    env.step(Action(type="probe"))
    env.step(Action(type="update_belief", payload={"network_partition": 0.9, "db_overload": 0.1}))
    post_mitigation = env.step(Action(type="safe_mitigation"))

    if post_mitigation["done"]:
        assert env.state["requires_fix_confirmation"] is False
    else:
        final = env.step(Action(type="commit_fix", payload={"fix": "reroute_traffic"}))
        assert final["done"] is True
        assert env.state["requires_fix_confirmation"] is False
