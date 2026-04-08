from fastapi.testclient import TestClient

from server.app import app


client = TestClient(app)


def test_root_and_web_render_interactive_ui() -> None:
    root_response = client.get("/")
    assert root_response.status_code == 200
    assert "text/html" in root_response.headers["content-type"]
    assert "RealityOps Arena" in root_response.text
    assert "Run Demo" in root_response.text

    web_response = client.get("/web")
    assert web_response.status_code == 200
    assert "RealityOps Arena" in web_response.text


def test_api_metadata_and_health() -> None:
    metadata = client.get("/api")
    assert metadata.status_code == 200
    payload = metadata.json()
    assert payload["service"] == "realityops-arena"
    assert "/" in payload["endpoints"]
    assert "/web" in payload["endpoints"]
    assert "/quick/demo" in payload["endpoints"]
    assert "/tasks" in payload["endpoints"]

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}


def test_reset_step_state_flow() -> None:
    reset_response = client.post("/reset", json={"task": "false_alarm"})
    assert reset_response.status_code == 200
    reset_payload = reset_response.json()
    assert reset_payload["done"] is False
    assert reset_payload["task"] == "false_alarm"
    assert "observation" in reset_payload

    step_response = client.post("/step", json={"type": "check_metrics"})
    assert step_response.status_code == 200
    step_payload = step_response.json()
    assert isinstance(step_payload["reward"], float)
    assert "info" in step_payload
    assert "task" in step_payload["info"]

    state_response = client.get("/state")
    assert state_response.status_code == 200
    state_payload = state_response.json()
    assert state_payload["task_name"] == "false_alarm"
    assert "score" in state_payload


def test_quick_endpoints() -> None:
    quick_reset = client.post("/quick/reset", json={"task": "ambiguous_root"})
    assert quick_reset.status_code == 200
    assert quick_reset.json()["task"] == "ambiguous_root"

    quick_step = client.post("/quick/step", json={"type": "check_logs"})
    assert quick_step.status_code == 200
    quick_step_payload = quick_step.json()
    assert "observation" in quick_step_payload
    assert "reward" in quick_step_payload

    demo = client.get("/quick/demo")
    assert demo.status_code == 200
    demo_payload = demo.json()
    assert demo_payload["task"] == "false_alarm"
    assert demo_payload["result"] in {"SUCCESS", "INCOMPLETE"}
    assert len(demo_payload["steps"]) >= 1
    assert demo_payload["steps"][0]["step"] == 0


def test_docs_endpoint_is_available() -> None:
    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "Swagger UI" in docs.text


def test_tasks_endpoint_lists_all_tasks() -> None:
    tasks = client.get("/tasks")
    assert tasks.status_code == 200
    payload = tasks.json()
    assert isinstance(payload, list)
    assert len(payload) >= 7
    assert "multi_incident" in payload


def test_reset_rejects_unsupported_task_literal() -> None:
    bad_task = client.post("/reset", json={"task": "unknown_task"})
    assert bad_task.status_code == 422


def test_step_rejects_non_object_payload_for_update_belief() -> None:
    bad_payload = client.post("/step", json={"type": "update_belief", "payload": "not-an-object"})
    assert bad_payload.status_code == 422


def test_state_exposes_scoring_components() -> None:
    client.post("/reset", json={"task": "ambiguous_root"})
    client.post("/step", json={"type": "check_logs"})
    state = client.get("/state")
    assert state.status_code == 200
    body = state.json()
    assert "score" in body
    assert "components" in body["score"]


def test_quick_demo_has_monotonic_steps() -> None:
    demo = client.get("/quick/demo")
    assert demo.status_code == 200
    steps = demo.json()["steps"]
    ids = [item["step"] for item in steps]
    assert ids == sorted(ids)
    assert ids[0] == 0


def test_invalid_action_is_rejected() -> None:
    invalid = client.post("/step", json={"type": "definitely_not_valid"})
    assert invalid.status_code == 422


def test_reset_accepts_seed_for_reproducibility() -> None:
    first = client.post("/reset", json={"task": "ambiguous_root", "seed": 1234})
    second = client.post("/reset", json={"task": "ambiguous_root", "seed": 1234})
    assert first.status_code == 200
    assert second.status_code == 200

    obs1 = first.json()["observation"]
    obs2 = second.json()["observation"]
    assert obs1["logs"] == obs2["logs"]
    assert obs1["metrics"] == obs2["metrics"]
    assert obs1["market_hours"] == obs2["market_hours"]
