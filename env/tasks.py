from __future__ import annotations

from typing import Dict

from .models import TaskName
from .worlds import WORLDS

TASK_SPECS: Dict[TaskName, Dict] = {
    "false_alarm": {
        "difficulty": "easy",
        "description": "Determine whether to avoid risky changes when alarms are mostly noisy.",
        "alert": "Intermittent latency alert in payments API",
        "candidate_worlds": {
            "no_incident": 0.72,
            "cache_bug": 0.16,
            "auth_expiry": 0.12,
        },
        "ground_truth_world": "no_incident",
        "max_steps": 6,
        "revenue_loss_per_step": 1800,
        "required_evidence": 2,
        "required_belief_updates": 0,
        "require_mitigation_before_fix": False,
    },
    "ambiguous_root": {
        "difficulty": "medium",
        "description": "Diagnose mixed signals and apply the right fix.",
        "alert": "Sustained checkout latency and intermittent 5xx errors",
        "candidate_worlds": {
            "db_overload": 0.40,
            "cache_bug": 0.30,
            "auth_expiry": 0.30,
        },
        "ground_truth_world": "db_overload",
        "max_steps": 8,
        "revenue_loss_per_step": 5000,
        "required_evidence": 2,
        "required_belief_updates": 1,
        "require_mitigation_before_fix": False,
    },
    "revenue_tradeoff": {
        "difficulty": "hard",
        "description": "Minimize business impact while selecting the correct root-cause fix.",
        "alert": "Global checkout degradation with sharp conversion drop",
        "candidate_worlds": {
            "network_partition": 0.45,
            "db_overload": 0.35,
            "cache_bug": 0.20,
        },
        "ground_truth_world": "network_partition",
        "max_steps": 8,
        "revenue_loss_per_step": 9000,
        "required_evidence": 3,
        "required_belief_updates": 1,
        "require_mitigation_before_fix": True,
    },
    "cascading_failure": {
        "difficulty": "hard",
        "description": "Handle compounding failure signals and restore auth stability.",
        "alert": "Cascading cross-service auth failures in production",
        "candidate_worlds": {
            "auth_expiry": 0.42,
            "network_partition": 0.34,
            "db_overload": 0.24,
        },
        "ground_truth_world": "auth_expiry",
        "max_steps": 10,
        "revenue_loss_per_step": 12000,
        "required_evidence": 3,
        "required_belief_updates": 2,
        "require_mitigation_before_fix": False,
    },
    "multi_incident": {
        "difficulty": "ultra-hard",
        "description": "Handle overlapping incidents with limited resources.",
        "alert": "Multiple simultaneous alerts: DB overload and network partition",
        "candidate_worlds": {
            "db_overload": 0.40,
            "network_partition": 0.40,
            "cache_bug": 0.10,
            "auth_expiry": 0.10,
        },
        "ground_truth_world": ["db_overload", "network_partition"],  # List for multiple
        "max_steps": 12,
        "revenue_loss_per_step": 15000,
        "required_evidence": 3,
        "required_belief_updates": 3,
        "require_mitigation_before_fix": True,
    },
    "security_breach": {
        "difficulty": "hard",
        "description": "Detect and respond to unauthorized access attempts.",
        "alert": "Unusual login patterns and data exfiltration indicators",
        "candidate_worlds": {
            "security_breach": 0.50,
            "no_incident": 0.30,
            "auth_expiry": 0.20,
        },
        "ground_truth_world": "security_breach",
        "max_steps": 8,
        "revenue_loss_per_step": 10000,
        "required_evidence": 2,
        "required_belief_updates": 1,
        "require_mitigation_before_fix": True,
    },
    "resource_exhaustion": {
        "difficulty": "medium",
        "description": "Manage resource limits during traffic spikes.",
        "alert": "Memory usage spiking with OOM errors",
        "candidate_worlds": {
            "resource_exhaustion": 0.60,
            "db_overload": 0.25,
            "cache_bug": 0.15,
        },
        "ground_truth_world": "resource_exhaustion",
        "max_steps": 7,
        "revenue_loss_per_step": 6000,
        "required_evidence": 2,
        "required_belief_updates": 1,
        "require_mitigation_before_fix": False,
    },
}


def task_names() -> list[TaskName]:
    return list(TASK_SPECS.keys())


def normalize_beliefs(raw_beliefs: Dict[str, float], allowed: Dict[str, float]) -> Dict[str, float]:
    cleaned = {
        world: max(0.0, float(raw_beliefs.get(world, 0.0)))
        for world in allowed
    }
    total = sum(cleaned.values())
    if total <= 0:
        fallback_total = sum(allowed.values())
        return {world: allowed[world] / fallback_total for world in allowed}
    return {world: cleaned[world] / total for world in cleaned}


def default_beliefs(task_name: TaskName) -> Dict[str, float]:
    allowed = TASK_SPECS[task_name]["candidate_worlds"]
    return normalize_beliefs(allowed, allowed)


def build_observation(state: Dict, seed: int = 42) -> Dict:
    import random
    random.seed(seed)
    task = state["task_spec"]
    beliefs = state["beliefs"]
    active_world_name = state["active_world"]
    if isinstance(active_world_name, list):
        # For multi-incident, use the first active world for observation
        active_world = WORLDS[active_world_name[0]]
    else:
        active_world = WORLDS[active_world_name]
    step = state["steps"]

    metrics = {"cpu": 0.0, "latency": 0.0, "error_rate": 0.0}
    for world_name, probability in beliefs.items():
        world_metrics = WORLDS[world_name]["metrics"]
        metrics["cpu"] += world_metrics["cpu"] * probability
        metrics["latency"] += world_metrics["latency"] * probability
        metrics["error_rate"] += world_metrics["error_rate"] * probability

    if state["investigations"]["check_metrics"]:
        metrics["cpu"] = 0.75 * active_world["metrics"]["cpu"] + 0.25 * metrics["cpu"]
        metrics["latency"] = 0.75 * active_world["metrics"]["latency"] + 0.25 * metrics["latency"]
        metrics["error_rate"] = 0.75 * active_world["metrics"]["error_rate"] + 0.25 * metrics["error_rate"]
    else:
        metrics["latency"] += step * 6
        metrics["error_rate"] += min(0.04, step * 0.006)

    logs = [
        "incident bridge started for payments service",
        "customer support reports intermittent checkout failures",
    ]
    # Dynamic noise
    if random.random() > 0.5:
        logs.append("Random noise: unrelated service log entry")
    if random.random() > 0.7:
        logs.append("Hint: Check metrics for anomalies")
    if state["investigations"]["check_logs"]:
        logs = active_world["logs"] + logs

        if task["difficulty"] == "hard" and not state["investigations"]["probe"]:
            distractor_world = sorted(
                task["candidate_worlds"].items(),
                key=lambda item: item[1],
                reverse=True,
            )
            distractor_name = next(
                (name for name, _ in distractor_world if name != active_world_name),
                None,
            )
            if distractor_name:
                logs = WORLDS[distractor_name]["logs"][:1] + logs

    slack = [
        "On-call: revenue dip is visible on the live dashboard.",
        "SRE lead: avoid blind production changes unless evidence is strong.",
    ]
    if state["investigations"]["probe"]:
        slack.append(f"Probe hint: {active_world['probe_hint']}")
    else:
        slack.append("Need a focused probe before we choose mitigation or fix.")

    # Add team responses if asked
    if state.get("team_queries", 0) > 0:
        team_responses = [
            "DevOps: 'DB is spiking—check connections!'",
            "SRE: 'Auth service might be overloaded.'",
            "On-call: 'Revenue drop correlates with latency.'"
        ]
        random.seed(state["seed"] + state["steps"])
        response = random.choice(team_responses)
        slack.append(response)

    if state.get("premature_fix_count", 0) > 0:
        slack.append("IC note: fix appears premature; collect stronger evidence before final rollout.")

    if state.get("requires_fix_confirmation") and state.get("applied_fix"):
        slack.append("SRE lead: keep validating, current fix is provisional until confidence gates pass.")

    alerts = [task["alert"]]
    if step >= max(2, task["max_steps"] - 2):
        alerts.append("Revenue impact accelerating; leadership requesting ETA.")

    if state.get("requires_fix_confirmation") and state.get("applied_fix"):
        alerts.append("Fix not yet confirmed by incident command checklist.")

    # Hints
    hints = []
    if not state["investigations"]["probe"]:
        hints.append("Consider probing for more evidence.")
    if state["belief_update_count"] < 1:
        hints.append("Update beliefs based on observations.")

    # Time-based dynamic events
    if step > 5:
        alerts.append("ESCALATION: Revenue loss accelerating—executives notified!")
        hints.append("Prioritize fixes to avoid further escalation.")
    if random.random() > 0.8 and step > 3:
        slack.append("SYSTEM: Unexpected traffic spike detected.")
        metrics["latency"] *= 1.2  # Simulate spike

    # Confidence levels
    confidence_levels = beliefs.copy()

    return {
        "alerts": alerts,
        "logs": logs[:6],
        "metrics": {
            "cpu": round(metrics["cpu"], 2),
            "latency": round(metrics["latency"], 2),
            "error_rate": round(metrics["error_rate"], 3),
        },
        "slack": slack[:4],
        "revenue_loss": float(state["revenue_loss"]),
        "confidence_levels": confidence_levels,
        "hints": hints,
        "market_hours": state.get("market_hours", True),
    }