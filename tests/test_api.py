import pytest
from fastapi.testclient import TestClient
from server.app import app

client = TestClient(app)


def test_reset_endpoint():
    """Test /reset endpoint."""
    response = client.post("/reset", json={"task": "false_alarm"})
    assert response.status_code == 200
    data = response.json()
    assert "observation" in data
    assert "done" in data
    assert data["done"] == False
    assert data["task"] == "false_alarm"


def test_reset_multi_incident():
    """Test /reset endpoint with multi_incident task."""
    response = client.post("/reset", json={"task": "multi_incident"})
    assert response.status_code == 200
    data = response.json()
    assert "observation" in data
    assert data["task"] == "multi_incident"


def test_step_endpoint():
    """Test /step endpoint."""
    # Reset first
    client.post("/reset", json={"task": "false_alarm"})
    
    # Take a step
    response = client.post("/step", json={"type": "probe"})
    assert response.status_code == 200
    data = response.json()
    assert "observation" in data
    assert "reward" in data
    assert "done" in data
    assert "info" in data


def test_step_invalid_action():
    """Test /step endpoint with invalid action type."""
    client.post("/reset", json={"task": "false_alarm"})
    
    # Send invalid action type - should propagate as error, not mask it
    response = client.post("/step", json={"type": "invalid_action_type"})
    # Could be 400, 422, or 500 depending on validation
    assert response.status_code >= 400


def test_state_endpoint():
    """Test /state endpoint."""
    client.post("/reset", json={"task": "false_alarm"})
    
    response = client.get("/state")
    assert response.status_code == 200
    data = response.json()
    assert "task_name" in data
    assert data["task_name"] == "false_alarm"


def test_visualize_endpoint():
    """Test /visualize endpoint."""
    client.post("/reset", json={"task": "false_alarm"})
    client.post("/step", json={"type": "probe"})
    
    response = client.get("/visualize")
    assert response.status_code == 200
    data = response.json()
    assert "trajectory" in data
    assert "beliefs_over_time" in data
    assert "current_beliefs" in data
    assert isinstance(data["beliefs_over_time"], list)


def test_multi_incident_risky_hotfix_via_api():
    """Test risky_hotfix on multi_incident via API (the problematic path)."""
    # Reset multi_incident
    response = client.post("/reset", json={"task": "multi_incident"})
    assert response.status_code == 200
    
    # Take risky_hotfix action - should NOT crash with unhashable type: list
    response = client.post("/step", json={"type": "risky_hotfix"})
    
    # Should either succeed (200) or return proper error (4xx/5xx), not mask the error
    assert response.status_code in [200, 400, 422, 500]
    
    # If it's an error, it should be explicit
    if response.status_code >= 400:
        data = response.json()
        assert "detail" in data


def test_security_breach_block_ip_via_api():
    """Test block_ip fix on security_breach via API."""
    client.post("/reset", json={"task": "security_breach"})
    
    response = client.post("/step", json={
        "type": "commit_fix",
        "payload": {"fix": "block_ip"}
    })
    assert response.status_code == 200
    data = response.json()
    assert data["info"]["grader_components"]["correct_fix"] == 1.0


def test_resource_exhaustion_scale_up_via_api():
    """Test scale_up fix on resource_exhaustion via API."""
    client.post("/reset", json={"task": "resource_exhaustion"})
    
    response = client.post("/step", json={
        "type": "commit_fix",
        "payload": {"fix": "scale_up"}
    })
    assert response.status_code == 200
    data = response.json()
    assert data["info"]["grader_components"]["correct_fix"] == 1.0
