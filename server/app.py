from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import uvicorn
from env.core import RealityOpsEnv
from env.models import Action, ResetRequest, ResetResponse, StepResponse
from env.tasks import task_names

app = FastAPI()
env = RealityOpsEnv()


def _as_dict(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()  # Pydantic v2
    return model.dict()  # Pydantic v1 fallback


SPACE_UI_HTML = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>RealityOps Arena</title>
    <style>
        :root {
            --bg: #0b1220;
            --panel: #121d33;
            --muted: #9ab0d5;
            --text: #f4f7ff;
            --accent: #4cc9f0;
            --accent2: #ff9f1c;
            --ok: #8bd450;
            --border: #26365b;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: "Trebuchet MS", "Segoe UI", sans-serif;
            color: var(--text);
            background:
                radial-gradient(circle at 15% 15%, rgba(76, 201, 240, 0.16), transparent 38%),
                radial-gradient(circle at 85% 0%, rgba(255, 159, 28, 0.14), transparent 32%),
                var(--bg);
            min-height: 100vh;
            padding: 20px;
        }
        .wrap {
            max-width: 980px;
            margin: 0 auto;
            display: grid;
            gap: 14px;
        }
        .card {
            background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 16px;
            box-shadow: 0 12px 35px rgba(0,0,0,0.28);
        }
        h1 {
            margin: 0 0 8px;
            letter-spacing: 0.4px;
        }
        p {
            margin: 6px 0;
            color: var(--muted);
        }
        a {
            color: var(--accent);
            text-decoration: none;
        }
        a:hover { text-decoration: underline; }
        .row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 10px;
            margin-top: 10px;
        }
        label { font-size: 13px; color: var(--muted); display: block; margin-bottom: 6px; }
        select, input, textarea, button {
            width: 100%;
            border-radius: 10px;
            border: 1px solid var(--border);
            background: #0f1730;
            color: var(--text);
            padding: 10px 12px;
            font-size: 14px;
        }
        textarea { min-height: 94px; font-family: ui-monospace, Menlo, Consolas, monospace; }
        button {
            cursor: pointer;
            border: none;
            font-weight: 700;
            background: linear-gradient(90deg, var(--accent), #3aa3ff);
            color: #041020;
            transition: transform 0.15s ease, filter 0.2s ease;
        }
        button.alt {
            background: linear-gradient(90deg, var(--accent2), #ffbe4d);
            color: #221200;
        }
        button.ghost {
            background: #17274a;
            color: var(--text);
            border: 1px solid var(--border);
        }
        button:hover { transform: translateY(-1px); filter: brightness(1.04); }
        .status { color: var(--ok); font-size: 13px; margin-top: 8px; }
        .meta {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-top: 8px;
        }
        .pill {
            font-size: 12px;
            padding: 6px 10px;
            border-radius: 999px;
            border: 1px solid var(--border);
            background: #101c39;
            color: var(--muted);
        }
        pre {
            margin: 0;
            background: #091126;
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 12px;
            overflow: auto;
            max-height: 45vh;
        }
    </style>
</head>
<body>
    <div class="wrap">
        <section class="card">
            <h1>RealityOps Arena</h1>
            <p>Run tasks directly from your Hugging Face Space UI.</p>
            <p><a href="/docs" target="_blank" rel="noopener noreferrer">Open API Docs</a> | <a href="/api" target="_blank" rel="noopener noreferrer">Service Metadata</a></p>
            <div class="row">
                <div>
                    <label for="task">Task</label>
                    <select id="task">
                        <option value="">random</option>
                        <option value="false_alarm">false_alarm</option>
                        <option value="ambiguous_root">ambiguous_root</option>
                        <option value="revenue_tradeoff">revenue_tradeoff</option>
                        <option value="cascading_failure">cascading_failure</option>
                        <option value="multi_incident">multi_incident</option>
                        <option value="security_breach">security_breach</option>
                        <option value="resource_exhaustion">resource_exhaustion</option>
                    </select>
                </div>
                <div style="display:flex; align-items:flex-end; gap:8px;">
                    <button id="btn-reset">Reset Episode</button>
                    <button class="ghost" id="btn-state">Get State</button>
                    <button class="ghost" id="btn-demo">Run Demo</button>
                </div>
            </div>
            <div class="meta">
                <span class="pill">Best flow: reset -> investigate -> update_belief -> fix</span>
                <span class="pill">Demo endpoint: /quick/demo</span>
            </div>
            <p class="status" id="status">Ready.</p>
        </section>

        <section class="card">
            <div class="row">
                <div>
                    <label for="action">Action</label>
                    <select id="action">
                        <option value="probe">probe</option>
                        <option value="check_logs">check_logs</option>
                        <option value="check_metrics">check_metrics</option>
                        <option value="update_belief">update_belief</option>
                        <option value="commit_fix">commit_fix</option>
                        <option value="safe_mitigation">safe_mitigation</option>
                        <option value="risky_hotfix">risky_hotfix</option>
                        <option value="ask_team">ask_team</option>
                        <option value="wait">wait</option>
                    </select>
                </div>
                <div>
                    <label for="fix">Fix (used by commit_fix)</label>
                    <select id="fix">
                        <option value="increase_pool">increase_pool</option>
                        <option value="flush_cache">flush_cache</option>
                        <option value="refresh_token">refresh_token</option>
                        <option value="reroute_traffic">reroute_traffic</option>
                        <option value="block_ip">block_ip</option>
                        <option value="scale_up">scale_up</option>
                        <option value="no_fix">no_fix</option>
                    </select>
                </div>
            </div>
            <div class="row">
                <div style="grid-column:1/-1;">
                    <label for="belief">Belief JSON (used by update_belief)</label>
                    <textarea id="belief">{"db_overload":0.2,"cache_bug":0.2,"auth_expiry":0.2,"network_partition":0.2,"no_incident":0.2}</textarea>
                </div>
            </div>
            <div class="row">
                <div style="display:flex; align-items:flex-end; gap:8px;">
                    <button class="alt" id="btn-step">Run Step</button>
                </div>
            </div>
        </section>

        <section class="card">
            <label>Response</label>
            <pre id="out">{}</pre>
        </section>
    </div>

    <script>
        const out = document.getElementById('out');
        const statusEl = document.getElementById('status');

        const print = (data) => {
            out.textContent = JSON.stringify(data, null, 2);
        };

        const setStatus = (text, isError = false) => {
            statusEl.textContent = text;
            statusEl.style.color = isError ? '#ff7a7a' : '#8bd450';
        };

        const callApi = async (path, method = 'GET', body) => {
            const res = await fetch(path, {
                method,
                headers: { 'content-type': 'application/json' },
                body: body ? JSON.stringify(body) : undefined,
            });
            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.detail || ('Request failed with status ' + res.status));
            }
            return data;
        };

        document.getElementById('btn-reset').addEventListener('click', async () => {
            try {
                const task = document.getElementById('task').value;
                setStatus('Resetting episode...');
                const payload = task ? { task } : {};
                const data = await callApi('/reset', 'POST', payload);
                print(data);
                setStatus('Reset complete.');
            } catch (err) {
                setStatus(err.message, true);
            }
        });

        document.getElementById('btn-state').addEventListener('click', async () => {
            try {
                setStatus('Fetching state...');
                const data = await callApi('/state');
                print(data);
                setStatus('State fetched.');
            } catch (err) {
                setStatus(err.message, true);
            }
        });

        document.getElementById('btn-demo').addEventListener('click', async () => {
            try {
                setStatus('Running quick demo...');
                const data = await callApi('/quick/demo');
                print(data);
                setStatus('Demo complete.');
            } catch (err) {
                setStatus(err.message, true);
            }
        });

        document.getElementById('btn-step').addEventListener('click', async () => {
            try {
                const type = document.getElementById('action').value;
                const fix = document.getElementById('fix').value;
                const beliefRaw = document.getElementById('belief').value;

                const action = { type };
                if (type === 'commit_fix') {
                    action.payload = { fix };
                }
                if (type === 'update_belief') {
                    action.payload = JSON.parse(beliefRaw);
                }

                setStatus('Running step...');
                const data = await callApi('/step', 'POST', action);
                print(data);
                setStatus('Step complete.');
            } catch (err) {
                setStatus(err.message, true);
            }
        });
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def root():
    return SPACE_UI_HTML


@app.get("/web", response_class=HTMLResponse)
def web_root():
    return SPACE_UI_HTML


@app.get("/api")
def api_info():
    return {
        "service": "realityops-arena",
        "status": "ok",
        "endpoints": [
            "/",
            "/web",
            "/reset",
            "/step",
            "/tasks",
            "/state",
            "/health",
            "/visualize",
            "/quick/reset",
            "/quick/step",
            "/quick/demo",
            "/docs",
        ],
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/tasks")
def tasks():
    return task_names()

@app.post("/reset", response_model=ResetResponse)
def reset(payload: Optional[ResetRequest] = None):
    selected_task = payload.task if payload else None
    selected_seed = payload.seed if payload else None
    obs = env.reset(task_name=selected_task, seed=selected_seed)
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


@app.post("/quick/reset", response_model=ResetResponse)
def quick_reset(payload: Optional[ResetRequest] = None):
    return reset(payload)


@app.post("/quick/step", response_model=StepResponse)
def quick_step(action: Action):
    return step(action)


@app.get("/quick/demo")
def quick_demo():
    demo_env = RealityOpsEnv()
    first_observation = demo_env.reset(task_name="false_alarm")

    trajectory = [
        {
            "step": 0,
            "action": "reset",
            "observation": _as_dict(first_observation),
            "reward": 0.0,
            "done": False,
        }
    ]

    scripted_actions = [
        Action(type="check_metrics"),
        Action(type="check_logs"),
        Action(type="wait"),
    ]

    for index, scripted_action in enumerate(scripted_actions, start=1):
        result = demo_env.step(scripted_action)
        trajectory.append(
            {
                "step": index,
                "action": scripted_action.type,
                "observation": _as_dict(result["observation"]),
                "reward": result["reward"],
                "done": result["done"],
                "info": result["info"],
            }
        )
        if result["done"]:
            break

    score = demo_env.score()
    return {
        "task": "false_alarm",
        "result": "SUCCESS" if demo_env.state.get("done") else "INCOMPLETE",
        "final_score": score.get("score", 0.0),
        "steps": trajectory,
        "message": "Use /reset and /step for stateful episodes; /quick/demo is a scripted walkthrough.",
    }


def main():
    uvicorn.run("server.app:app", host="0.0.0.0", port=7860)


if __name__ == "__main__":
    main()