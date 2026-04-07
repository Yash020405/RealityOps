from typing import Optional
from fastapi import FastAPI, HTTPException
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
    except TypeError as e:
        # Specific handling for type errors (e.g., unhashable type)
        raise HTTPException(status_code=422, detail=f"Invalid action or state: {str(e)}")
    except ValueError as e:
        # Specific handling for value errors
        raise HTTPException(status_code=400, detail=f"Invalid action value: {str(e)}")
    except KeyError as e:
        # Specific handling for missing keys
        raise HTTPException(status_code=500, detail=f"Internal state error: {str(e)}")
    except Exception as e:
        # Re-raise unexpected exceptions to propagate as 500 errors
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/state")
def state():
    return env.state_view()


@app.get("/visualize")
def visualize():
    return {
        "trajectory": env.state["action_history"],
        "beliefs_over_time": env.state.get("belief_history", []),
        "current_beliefs": env.state["beliefs"],
        "task": env.state["task_name"],
        "steps": env.state["steps"],
        "revenue_loss": env.state["revenue_loss"],
    }


def main():
    uvicorn.run("server.app:app", host="0.0.0.0", port=7860)


if __name__ == "__main__":
    main()