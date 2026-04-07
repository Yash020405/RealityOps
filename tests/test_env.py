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