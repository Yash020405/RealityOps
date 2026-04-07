import pytest
from env.core import RealityOpsEnv
from env.models import Action


def test_reset():
    env = RealityOpsEnv()
    obs = env.reset("false_alarm")
    assert obs.step == 0
    assert "alerts" in obs.__dict__
    assert "confidence_levels" in obs.__dict__
    assert "hints" in obs.__dict__


def test_step():
    env = RealityOpsEnv()
    env.reset("false_alarm")
    action = Action(type="probe")
    result = env.step(action)
    assert "observation" in result
    assert "reward" in result
    assert "done" in result
    assert "info" in result


def test_multi_incident():
    env = RealityOpsEnv()
    obs = env.reset("multi_incident")
    assert obs.step == 0


def test_security_breach():
    env = RealityOpsEnv()
    obs = env.reset("security_breach")
    assert obs.step == 0
    assert "Unusual login patterns" in obs.alerts[0]


def test_resource_exhaustion():
    env = RealityOpsEnv()
    obs = env.reset("resource_exhaustion")
    assert obs.step == 0
    assert "Memory usage spiking" in obs.alerts[0]


def test_market_hours():
    env = RealityOpsEnv()
    obs = env.reset("false_alarm")
    assert hasattr(obs, 'market_hours')
    assert isinstance(obs.market_hours, bool)


def test_multi_incident_risky_hotfix():
    """Test that risky_hotfix doesn't crash on multi-incident (risky path grading)."""
    env = RealityOpsEnv()
    env.reset("multi_incident")
    
    # Apply risky_hotfix - this should not crash even though active_world is a list
    action = Action(type="risky_hotfix")
    result = env.step(action)
    
    assert "observation" in result
    assert "reward" in result
    assert "done" in result
    assert "info" in result
    # The action should be recorded in history
    assert len(env.state["action_history"]) > 0


def test_multi_incident_update_belief():
    """Test belief update on multi-incident with list active_world."""
    env = RealityOpsEnv()
    env.reset("multi_incident")
    
    # Update belief - should handle list active_world correctly
    action = Action(
        type="update_belief",
        payload={"db_overload": 0.6, "network_partition": 0.4}
    )
    result = env.step(action)
    
    assert result["reward"] is not None
    assert "belief_alignment" in result["info"]["reward_components"]


def test_multi_incident_creative_risky_fix():
    """Test creativity bonus calculation for multi-incident risky fixes."""
    env = RealityOpsEnv()
    env.reset("multi_incident")
    
    # First, mark that risky action was used
    action = Action(type="risky_hotfix")
    env.step(action)
    
    # Then commit a fix that matches one of the worlds
    action = Action(type="commit_fix", payload={"fix": "increase_pool"})
    result = env.step(action)
    
    # Should have processed without crashing
    assert result["reward"] is not None
    grader_info = result["info"].get("grader_components", {})
    assert "creativity_bonus" in grader_info or "correct_fix" in grader_info


def test_multi_incident_valid_fixes():
    """Test that all valid fixes are accepted for new tasks."""
    env = RealityOpsEnv()
    
    # Test security_breach with block_ip
    env.reset("security_breach")
    action = Action(type="commit_fix", payload={"fix": "block_ip"})
    result = env.step(action)
    assert result["info"]["grader_components"]["correct_fix"] == 1.0
    
    # Test resource_exhaustion with scale_up
    env.reset("resource_exhaustion")
    action = Action(type="commit_fix", payload={"fix": "scale_up"})
    result = env.step(action)
    assert result["info"]["grader_components"]["correct_fix"] == 1.0