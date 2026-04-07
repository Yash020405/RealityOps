from typing import Optional

from fastapi import FastAPI
import uvicorn
from env.core import RealityOpsEnv
from env.models import Action, Observation, ResetRequest, ResetResponse, StepResponse

app = FastAPI()
env = RealityOpsEnv()

@app.post("/reset", response_model=ResetResponse)
def reset(payload: Optional[ResetRequest] = None):
    selected_task = payload.task if payload else None
    obs = env.reset(task_name=selected_task)
    return ResetResponse(observation=obs, done=False, task=env.state["task_name"])

@app.post("/step", response_model=StepResponse)
def step(action: Action):
    try:
        result = env.step(action)
        return StepResponse(
            observation=result["observation"],
            reward=result["reward"],
            done=result["done"],
            info=result["info"],
        )
    except Exception as e:
        return StepResponse(
            observation=Observation(
                alerts=["Error occurred"],
                logs=["Internal error"],
                metrics={"cpu": 0.0, "latency": 0.0, "error_rate": 0.0},
                slack=["System error"],
                revenue_loss=0.0,
                step=env.state["steps"],
                confidence_levels={},
                hints=["Check action format"],
            ),
            reward=0.0,
            done=True,
            info={"error": str(e)},
        )

@app.get("/state")
def state():
    return env.state_view()


@app.get("/visualize")
def visualize():
    return {
        "trajectory": env.state["action_history"],
        "beliefs_over_time": getattr(env.state, "belief_history", []),
        "current_beliefs": env.state["beliefs"],
        "task": env.state["task_name"],
        "steps": env.state["steps"],
        "revenue_loss": env.state["revenue_loss"],
    }


def main():
    uvicorn.run("server.app:app", host="0.0.0.0", port=7860)


if __name__ == "__main__":
    main()