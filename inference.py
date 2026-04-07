import json
import os
from typing import Dict, List, Optional

import requests
from openai import OpenAI

LLM_API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
ENV_BASE_URL = os.getenv("ENV_BASE_URL", "http://localhost:7860")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
HF_TOKEN = os.getenv("HF_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
API_KEY = HF_TOKEN or OPENAI_API_KEY or os.getenv("API_KEY")
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")

BENCHMARK = "realityops_arena"
TASKS = [
    "false_alarm",
    "ambiguous_root",
    "revenue_tradeoff",
    "cascading_failure",
    "multi_incident",
    "security_breach",
    "resource_exhaustion",
]
MAX_STEPS = 10
SUCCESS_SCORE_THRESHOLD = 0.45
TEMPERATURE = 0.0
MAX_TOKENS = 220


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_value = error if error else "null"
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={str(done).lower()} error={error_value}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{value:.2f}" for value in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}",
        flush=True,
    )


def action_to_text(action: Dict) -> str:
    action_type = action.get("type", "wait")
    payload = action.get("payload")
    if payload:
        payload_text = ",".join(f"{key}={value}" for key, value in sorted(payload.items()))
        return f"{action_type}({payload_text})"
    return action_type


def _safe_json_parse(raw: str) -> Optional[Dict]:
    text = (raw or "").strip()
    if not text:
        return None

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
    return None


def _heuristic_action(task: str, observation: Dict, step: int, history: List[Dict], info: Dict) -> Dict:
    logs_blob = " ".join(observation.get("logs", [])).lower()
    metrics = observation.get("metrics", {})
    latency = float(metrics.get("latency", 0.0))
    error_rate = float(metrics.get("error_rate", 0.0))
    needs_confirmation = bool(info.get("requires_fix_confirmation", False))

    def _has_action(name: str) -> bool:
        return any(item.get("type") == name for item in history)

    def _best_fix() -> str:
        if "pool exhausted" in logs_blob or "connection timeout to primary-db" in logs_blob:
            return "increase_pool"
        if "stale cache key" in logs_blob or "redis spike" in logs_blob:
            return "flush_cache"
        if "auth failure" in logs_blob or "token expired" in logs_blob:
            return "refresh_token"
        if "packet loss" in logs_blob or latency > 360:
            return "reroute_traffic"
        if "unusual login" in logs_blob or "data export volume spike" in logs_blob:
            return "block_ip"
        if "OOM killer" in logs_blob or "memory pressure" in logs_blob:
            return "scale_up"
        return "increase_pool"

    if task == "false_alarm":
        if step == 1:
            return {"type": "check_metrics"}
        if step == 2:
            return {"type": "check_logs"}
        if step == 3 and not _has_action("probe"):
            return {"type": "probe"}
        if error_rate <= 0.06 and latency < 240:
            return {"type": "wait"}
        return {"type": "safe_mitigation"}

    if task == "ambiguous_root":
        if not _has_action("check_logs"):
            return {"type": "check_logs"}
        if not _has_action("check_metrics"):
            return {"type": "check_metrics"}
        if not _has_action("probe"):
            return {"type": "probe"}
        if not _has_action("update_belief"):
            return {
                "type": "update_belief",
                "payload": {
                    "db_overload": 0.52,
                    "cache_bug": 0.18,
                    "auth_expiry": 0.16,
                    "network_partition": 0.10,
                    "no_incident": 0.04,
                },
            }
        if not _has_action("commit_fix") or needs_confirmation:
            return {"type": "commit_fix", "payload": {"fix": _best_fix()}}
        return {"type": "wait"}

    if task == "revenue_tradeoff":
        if not _has_action("check_logs"):
            return {"type": "check_logs"}
        if not _has_action("check_metrics"):
            return {"type": "check_metrics"}
        if not _has_action("probe"):
            return {"type": "probe"}
        if not _has_action("update_belief"):
            return {
                "type": "update_belief",
                "payload": {
                    "network_partition": 0.56,
                    "db_overload": 0.23,
                    "cache_bug": 0.15,
                    "auth_expiry": 0.04,
                    "no_incident": 0.02,
                },
            }
        if not _has_action("safe_mitigation"):
            return {"type": "safe_mitigation"}
        if not _has_action("commit_fix") or needs_confirmation:
            return {"type": "commit_fix", "payload": {"fix": _best_fix()}}
        return {"type": "wait"}

    if task == "cascading_failure":
        if not _has_action("check_logs"):
            return {"type": "check_logs"}
        if not _has_action("probe"):
            return {"type": "probe"}
        if not _has_action("check_metrics"):
            return {"type": "check_metrics"}
        belief_updates = sum(1 for item in history if item.get("type") == "update_belief")
        if belief_updates < 2:
            return {
                "type": "update_belief",
                "payload": {
                    "auth_expiry": 0.51 if belief_updates == 0 else 0.62,
                    "network_partition": 0.24,
                    "db_overload": 0.16,
                    "cache_bug": 0.06,
                    "no_incident": 0.02,
                },
            }
        if not _has_action("commit_fix") or needs_confirmation:
            return {"type": "commit_fix", "payload": {"fix": _best_fix()}}
        return {"type": "wait"}

    if task == "security_breach":
        if not _has_action("check_logs"):
            return {"type": "check_logs"}
        if not _has_action("check_metrics"):
            return {"type": "check_metrics"}
        if not _has_action("probe"):
            return {"type": "probe"}
        if not _has_action("update_belief"):
            return {
                "type": "update_belief",
                "payload": {
                    "security_breach": 0.50,
                    "no_incident": 0.30,
                    "auth_expiry": 0.20,
                },
            }
        if not _has_action("safe_mitigation"):
            return {"type": "safe_mitigation"}
        if not _has_action("commit_fix") or needs_confirmation:
            return {"type": "commit_fix", "payload": {"fix": _best_fix()}}
        return {"type": "wait"}

    if task == "resource_exhaustion":
        if not _has_action("check_metrics"):
            return {"type": "check_metrics"}
        if not _has_action("check_logs"):
            return {"type": "check_logs"}
        if not _has_action("probe"):
            return {"type": "probe"}
        if not _has_action("update_belief"):
            return {
                "type": "update_belief",
                "payload": {
                    "resource_exhaustion": 0.60,
                    "db_overload": 0.25,
                    "cache_bug": 0.15,
                },
            }
        if not _has_action("commit_fix") or needs_confirmation:
            return {"type": "commit_fix", "payload": {"fix": _best_fix()}}
        return {"type": "wait"}

    belief_payload = {
        "db_overload": 0.35,
        "cache_bug": 0.20,
        "auth_expiry": 0.20,
        "network_partition": 0.20,
        "no_incident": 0.05,
    }
    if error_rate < 0.07:
        belief_payload["no_incident"] = 0.30
    return {"type": "update_belief", "payload": belief_payload}


def _model_action(
    client: Optional[OpenAI],
    task: str,
    observation: Dict,
    history: List[Dict],
) -> Optional[Dict]:
    if client is None:
        return None

    prompt = {
        "task": task,
        "observation": observation,
        "history": history[-5:],
        "allowed_actions": [
            "probe",
            "check_logs",
            "check_metrics",
            "update_belief",
            "commit_fix",
            "safe_mitigation",
            "risky_hotfix",
            "wait",
        ],
        "fix_options": [
            "increase_pool",
            "flush_cache",
            "refresh_token",
            "reroute_traffic",
            "block_ip",
            "scale_up",
            "no_fix",
        ],
        "instruction": "Return ONLY valid JSON with keys: type (string) and optional payload (object).",
    }

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": "You are an SRE agent. Produce one safe, high-signal next action as JSON only.",
                },
                {"role": "user", "content": json.dumps(prompt)},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            stream=False,
        )
        raw = completion.choices[0].message.content or ""
        parsed = _safe_json_parse(raw)
        if parsed and isinstance(parsed.get("type"), str):
            return parsed
    except Exception:
        return None

    return None


def _sanitize_action(candidate: Dict) -> Dict:
    allowed = {
        "probe",
        "check_logs",
        "check_metrics",
        "update_belief",
        "commit_fix",
        "safe_mitigation",
        "risky_hotfix",
        "wait",
    }
    action_type = candidate.get("type", "wait")
    if action_type not in allowed:
        return {"type": "wait"}

    payload = candidate.get("payload")
    if payload is not None and not isinstance(payload, dict):
        payload = None

    result = {"type": action_type}
    if payload:
        result["payload"] = payload
    return result


def _run_episode(client: Optional[OpenAI], task: str) -> None:
    rewards: List[float] = []
    history: List[Dict] = []
    steps = 0
    score = 0.0
    success = False
    last_info: Dict = {}

    log_start(task=task, env=BENCHMARK, model=MODEL_NAME)

    try:
        reset_res = requests.post(f"{ENV_BASE_URL}/reset", json={"task": task}, timeout=30)
        reset_res.raise_for_status()
        reset_body = reset_res.json()
        observation = reset_body["observation"]
        done = bool(reset_body.get("done", False))

        while not done and steps < MAX_STEPS:
            steps += 1

            model_candidate = _model_action(client, task, observation, history)
            if model_candidate is None:
                model_candidate = _heuristic_action(task, observation, steps, history, last_info)

            action = _sanitize_action(model_candidate)
            step_error: Optional[str] = None

            try:
                step_res = requests.post(f"{ENV_BASE_URL}/step", json=action, timeout=30)
                step_res.raise_for_status()
                step_body = step_res.json()
                reward = float(step_body.get("reward", 0.0))
                done = bool(step_body.get("done", False))
                observation = step_body.get("observation", {})
                info = step_body.get("info", {})
                last_info = info if isinstance(info, dict) else {}
                error_value = info.get("last_action_error")
                step_error = str(error_value) if error_value else None
            except Exception as exc:
                reward = 0.0
                done = True
                step_error = str(exc)

            rewards.append(reward)
            history.append({"step": steps, "type": action.get("type"), "reward": reward})
            log_step(
                step=steps,
                action=action_to_text(action),
                reward=reward,
                done=done,
                error=step_error,
            )

        try:
            state_res = requests.get(f"{ENV_BASE_URL}/state", timeout=30)
            state_res.raise_for_status()
            state_body = state_res.json()
            score = float(state_body.get("score", {}).get("score", 0.0))
        except Exception:
            score = min(max(sum(rewards) / max(1, len(rewards)), 0.0), 1.0)

        success = score >= SUCCESS_SCORE_THRESHOLD

    except Exception:
        success = False
        score = 0.0
        steps = max(steps, 1)
        if not rewards:
            rewards = [0.0]

    finally:
        log_end(success=success, steps=steps, score=score, rewards=rewards)


def main() -> None:
    _ = LOCAL_IMAGE_NAME
    client = OpenAI(base_url=LLM_API_BASE_URL, api_key=API_KEY) if API_KEY else None
    selected_tasks = [os.getenv("TASK_NAME")] if os.getenv("TASK_NAME") else TASKS
    for task in selected_tasks:
        _run_episode(client, task)


if __name__ == "__main__":
    main()