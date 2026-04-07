from __future__ import annotations

import logging
from copy import deepcopy
from typing import Dict, Optional

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from .models import Action, Observation, Reward, TaskName
from .worlds import WORLDS
from .tasks import TASK_SPECS, build_observation, default_beliefs, normalize_beliefs
from .grader import grade

class RealityOpsEnv:

    def __init__(self):
        self.state = {}
        self.reset()

    def _selected_task(self, requested: Optional[str]) -> TaskName:
        if requested in TASK_SPECS:
            return requested  # type: ignore[return-value]
        return "ambiguous_root"

    def reset(self, task_name: Optional[str] = None):
        import random
        selected_task = self._selected_task(task_name)
        task_spec = deepcopy(TASK_SPECS[selected_task])

        seed = random.randint(0, 10000)
        self.state = {
            "task_name": selected_task,
            "task_spec": task_spec,
            "worlds": WORLDS,
            "active_world": task_spec["ground_truth_world"],
            "beliefs": default_beliefs(selected_task),
            "applied_fix": None,
            "requires_fix_confirmation": False,
            "mitigation_applied": False,
            "mitigation_step": None,
            "fix_step": None,
            "risky_used": False,
            "repeat_actions": 0,
            "premature_fix_count": 0,
            "invalid_fix_count": 0,
            "belief_update_count": 0,
            "wait_count": 0,
            "investigations": {
                "probe": False,
                "check_logs": False,
                "check_metrics": False,
            },
            "action_history": [],
            "reward_history": [],
            "steps": 0,
            "done": False,
            "revenue_loss": 0.0,
            "episode_score": 0.0,
            "seed": seed,
            "team_queries": 0,
            "belief_history": [default_beliefs(selected_task)],
            "market_hours": random.choice([True, False]),  # Affects revenue impact
        }

        obs = build_observation(self.state, seed)
        logger.info(f"Episode reset for task: {selected_task}, seed: {seed}")
        return Observation(**obs, step=0)

    def _reward_from_action(self, action: Action) -> Reward:
        components: Dict[str, float] = {
            "time_penalty": -self.state["task_spec"]["revenue_loss_per_step"] / 100000.0
        }

        history = self.state["action_history"]
        if history and history[-1]["type"] == action.type:
            self.state["repeat_actions"] += 1
            components["repetition_penalty"] = -0.06

        if action.type == "wait":
            self.state["wait_count"] += 1

        if action.type in self.state["investigations"]:
            first_time = not self.state["investigations"][action.type]
            self.state["investigations"][action.type] = True
            components["investigation"] = 0.08 if first_time else 0.02

        if action.type == "update_belief":
            payload = action.payload or {}
            normalized = normalize_beliefs(payload, self.state["task_spec"]["candidate_worlds"])
            self.state["beliefs"] = normalized
            self.state["belief_update_count"] += 1
            components["belief_update"] = 0.05
            components["belief_signal"] = 0.05  # Additional signal
            if isinstance(self.state["active_world"], list):
                alignment = sum(normalized.get(w, 0.0) for w in self.state["active_world"]) / len(self.state["active_world"])
            else:
                alignment = normalized.get(self.state["active_world"], 0.0)
            components["belief_alignment"] = 0.20 * alignment
            self.state["belief_history"].append(normalized.copy())

        elif action.type == "commit_fix":
            proposed_fix = (action.payload or {}).get("fix", "")
            self.state["applied_fix"] = proposed_fix
            self.state["fix_step"] = self.state["steps"]
            active_worlds = self.state["active_world"]
            if isinstance(active_worlds, list):
                correct_fixes = [WORLDS[world]["fix"] for world in active_worlds]
                correct_fix = correct_fixes  # List
            else:
                correct_fix = WORLDS[active_worlds]["fix"]
            evidence_count = sum(1 for value in self.state["investigations"].values() if value)
            required_evidence = self.state["task_spec"].get("required_evidence", 1)
            required_updates = self.state["task_spec"].get("required_belief_updates", 0)

            if evidence_count < required_evidence or self.state["belief_update_count"] < required_updates:
                self.state["requires_fix_confirmation"] = True
                self.state["premature_fix_count"] += 1
                components["premature_fix_penalty"] = -0.20
            else:
                self.state["requires_fix_confirmation"] = False

            valid_fixes = {"increase_pool", "flush_cache", "refresh_token", "reroute_traffic", "block_ip", "scale_up", "no_fix"}
            if proposed_fix and proposed_fix not in valid_fixes:
                self.state["invalid_fix_count"] += 1
                components["invalid_fix_penalty"] = -0.25

            if isinstance(correct_fix, list):
                if proposed_fix in correct_fix:
                    components["fix_quality"] = 0.55 / len(correct_fix)  # Partial credit
                else:
                    components["fix_quality"] = -0.35
            else:
                if proposed_fix == correct_fix:
                    components["fix_quality"] = 0.55
                elif self.state["active_world"] == "no_incident" and proposed_fix == "no_fix":
                    components["fix_quality"] = 0.45
                else:
                    components["fix_quality"] = -0.35

        elif action.type == "safe_mitigation":
            if not self.state["mitigation_applied"]:
                self.state["mitigation_applied"] = True
                self.state["mitigation_step"] = self.state["steps"]
                components["mitigation"] = 0.12
            else:
                components["mitigation"] = 0.03

        elif action.type == "risky_hotfix":
            self.state["risky_used"] = True
            self.state["applied_fix"] = (action.payload or {}).get("fix", "")
            self.state["fix_step"] = self.state["steps"]
            self.state["requires_fix_confirmation"] = True
            components["risky_penalty"] = -0.45

        elif action.type == "ask_team":
            self.state["team_queries"] = self.state.get("team_queries", 0) + 1
            components["team_help"] = -0.02  # Small cost
            # Add dynamic team response to slack
            team_responses = [
                "DevOps: 'DB is spiking—check connections!'",
                "SRE: 'Auth service might be overloaded.'",
                "On-call: 'Revenue drop correlates with latency.'"
            ]
            import random
            random.seed(self.state["seed"] + self.state["steps"])
            response = random.choice(team_responses)
            # Note: Slack is built in build_observation, so we can't modify here directly.
            # Instead, add a flag for build_observation to include team response.

        elif action.type == "wait":
            evidence_count = sum(1 for value in self.state["investigations"].values() if value)
            if self.state["task_name"] == "false_alarm" and evidence_count >= 2:
                components["wait_quality"] = 0.08
            else:
                components["wait_quality"] = -0.07
            if self.state["wait_count"] > 3:
                components["wait_penalty"] = -0.1

        raw_total = sum(components.values())
        normalized = max(0.0, min(1.0, 0.5 + raw_total))
        return Reward(value=normalized, components=components)

    def _is_done(self, action: Action) -> bool:
        if self.state["steps"] >= self.state["task_spec"]["max_steps"]:
            return True

        evidence_count = sum(1 for value in self.state["investigations"].values() if value)
        required_evidence = self.state["task_spec"].get("required_evidence", 1)
        required_updates = self.state["task_spec"].get("required_belief_updates", 0)
        has_confidence = (
            evidence_count >= required_evidence
            and self.state["belief_update_count"] >= required_updates
        )

        if (
            self.state["task_spec"].get("require_mitigation_before_fix", False)
            and self.state["applied_fix"] is not None
        ):
            has_confidence = has_confidence and self.state["mitigation_step"] is not None

        if action.type in ("commit_fix", "risky_hotfix") and self.state["applied_fix"] is not None:
            if has_confidence:
                self.state["requires_fix_confirmation"] = False
                return True
            return False

        if (
            self.state["task_name"] == "false_alarm"
            and action.type in ("wait", "safe_mitigation")
            and evidence_count >= 2
        ):
            return True

        if self.state["applied_fix"] is not None and action.type in ("wait", "safe_mitigation", "update_belief"):
            if has_confidence:
                self.state["requires_fix_confirmation"] = False
                return True

        return False

    def step(self, action: Action):
        if self.state.get("done"):
            obs = build_observation(self.state, self.state["seed"])
            return {
                "observation": Observation(**obs, step=self.state["steps"]),
                "reward": 0.0,
                "done": True,
                "info": {
                    "task": self.state["task_name"],
                    "message": "Episode already complete. Call reset().",
                    "score": self.state["episode_score"],
                    "reward_components": {},
                },
            }

        self.state["steps"] += 1
        step = self.state["steps"]
        self.state["action_history"].append({"step": step, "type": action.type, "payload": action.payload or {}})
        logger.debug(f"Step {step}: Action {action.type}, Payload {action.payload}")

        reward = self._reward_from_action(action)

        partial_reward = 0.0
        if action.type in ["probe", "check_logs", "check_metrics"] and not self.state["investigations"][action.type]:
            partial_reward += 0.1  # Signal progress
        reward.value += partial_reward

        self.state["revenue_loss"] += float(self.state["task_spec"]["revenue_loss_per_step"]) * (0.5 if not self.state["market_hours"] else 1.0)

        done = self._is_done(action)
        self.state["done"] = done

        grade_result = grade(self.state, WORLDS)
        self.state["episode_score"] = grade_result["score"]
        self.state["reward_history"].append(reward.value)

        obs = build_observation(self.state, self.state["seed"])

        return {
            "observation": Observation(**obs, step=step),
            "reward": reward.value,
            "done": done,
            "info": {
                "task": self.state["task_name"],
                "difficulty": self.state["task_spec"]["difficulty"],
                "score": grade_result["score"],
                "grader_components": grade_result["components"],
                "reward_components": reward.components,
                "remaining_steps": max(0, self.state["task_spec"]["max_steps"] - step),
                "requires_fix_confirmation": self.state["requires_fix_confirmation"],
            },
        }

    def state_view(self):
        score_result = grade(self.state, WORLDS)
        return {
            **self.state,
            "score": score_result,
        }

    def score(self):
        return grade(self.state, WORLDS)