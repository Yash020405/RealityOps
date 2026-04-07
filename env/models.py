from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal, Optional

TaskName = Literal[
    "false_alarm",
    "ambiguous_root",
    "revenue_tradeoff",
    "cascading_failure",
    "multi_incident",
    "security_breach",
    "resource_exhaustion",
]

class Observation(BaseModel):
    alerts: List[str]
    logs: List[str]
    metrics: Dict[str, float]
    slack: List[str]
    revenue_loss: float
    step: int
    confidence_levels: Dict[str, float] = Field(default_factory=dict)
    hints: List[str] = Field(default_factory=list)
    market_hours: bool = Field(default=False)

class Action(BaseModel):
    type: Literal[
        "probe",
        "check_logs",
        "check_metrics",
        "update_belief",
        "commit_fix",
        "safe_mitigation",
        "risky_hotfix",
        "ask_team",
        "wait"
    ]
    payload: Optional[Dict] = None


class Reward(BaseModel):
    value: float
    components: Dict[str, float] = Field(default_factory=dict)


class ResetRequest(BaseModel):
    task: Optional[TaskName] = None


class ResetResponse(BaseModel):
    observation: Observation
    done: bool
    task: TaskName


class StepResponse(BaseModel):
    observation: Observation
    reward: float
    done: bool
    info: Dict[str, Any]