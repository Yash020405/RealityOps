---
title: RealityOps Arena
emoji: ⚙️
colorFrom: blue
colorTo: red
sdk: docker
app_port: 7860
tags:
  - openenv
---

# RealityOps Arena

## Published Links

- GitHub: https://github.com/Yash020405/RealityOps
- Hugging Face Space (page): https://huggingface.co/spaces/thetallinnov8r/realityops
- Hugging Face runtime URL: https://thetallinnov8r-realityops.hf.space
- Built-in web UI routes: `https://thetallinnov8r-realityops.hf.space/` and `https://thetallinnov8r-realityops.hf.space/web`


## Local Development

To run the project locally:

1. Install dependencies: `pip install -r requirements.txt`
2. Start the API server: `uvicorn server.app:app --host 0.0.0.0 --port 7860`
3. Open the built-in UI at `http://localhost:7860/` or `http://localhost:7860/web`

Optional local Streamlit sandbox (separate process):
- Run `streamlit run server/ui.py`
- Access it at `http://localhost:8501`
- It connects to the API server at `http://localhost:7860` by default.

The environment models work that real SRE and platform engineers do:
- triaging active incidents
- distinguishing true incidents from noisy alerts
- choosing mitigations and fixes under time pressure
- minimizing revenue impact while preserving safety

## OpenEnv API

The server implements the standard endpoints:
- POST /reset -> returns initial observation and done=false
- POST /step -> returns observation, reward, done, info
- GET /tasks -> returns task catalog
- GET /state -> returns full internal state plus deterministic grader score
- GET /visualize -> returns episode trajectory and belief history

### API Examples

Reset a task:
```bash
curl -X POST http://localhost:7860/reset \
  -H "Content-Type: application/json" \
  -d '{"task": "false_alarm"}'
```

Take a step:
```bash
curl -X POST http://localhost:7860/step \
  -H "Content-Type: application/json" \
  -d '{"type": "probe"}'
```

Visualize episode:
```bash
curl http://localhost:7860/visualize
```

Typed Pydantic models are defined in env/models.py:
- Observation
- Action
- Reward
- ResetRequest / ResetResponse / StepResponse

## Action Space

- probe
- check_logs
- check_metrics
- update_belief
- commit_fix
- safe_mitigation
- risky_hotfix
- wait

Supported commit_fix payload values:
- increase_pool
- flush_cache
- refresh_token
- reroute_traffic
- block_ip
- scale_up
- no_fix

## Observation Space

- alerts: active incident warnings
- logs: mixed high-signal and noisy production logs (with dynamic noise for replayability)
- metrics: cpu, latency, error_rate
- slack: human team communication noise and hints
- revenue_loss: cumulative business impact
- step: current timestep
- confidence_levels: dict of belief probabilities for each world
- hints: contextual guidance (e.g., "Consider probing for more evidence")
- market_hours: boolean indicating if incident occurs during peak business hours (affects revenue impact)

## Tasks (Easy -> Hard)

RealityOps ships with seven tasks (exceeding minimum requirement):

1. false_alarm (easy)
- Objective: avoid unnecessary risky changes when alerts are mostly noise.
- Ground truth: no_incident.

2. ambiguous_root (medium)
- Objective: disambiguate mixed signals and apply the correct remediation.
- Ground truth: db_overload.

3. revenue_tradeoff (hard)
- Objective: limit revenue loss while still finding and applying the correct fix.
- Ground truth: network_partition.
- Additional gate: mitigation must happen before a fix is considered final.

4. cascading_failure (hard)
- Objective: coordinate evidence gathering and belief updates before committing fix.
- Ground truth: auth_expiry.
- Additional gate: at least two belief updates are required for full-confidence completion.

5. multi_incident (ultra-hard)
- Objective: handle overlapping incidents with limited resources.
- Ground truth: db_overload and network_partition (multi-world scenario).
- Additional gate: requires multiple belief updates and coordinated fixes.

6. security_breach (hard)
- Objective: detect and respond to unauthorized access attempts.
- Ground truth: security_breach.
- Additional gate: mitigation must happen before a fix is considered final.

7. resource_exhaustion (medium)
- Objective: manage resource limits during traffic spikes.
- Ground truth: resource_exhaustion.

## Advanced Features

- **Time-Based Events**: Escalation after step 5 with executive notifications
- **Team Interactions**: `ask_team` action for querying SRE colleagues
- **Dynamic Observations**: Evolving logs, metrics, and slack messages
- **Market Hours Impact**: Revenue loss halved during off-peak hours
- **Rich Belief Tracking**: Confidence levels and belief history
- **Interactive Web UI**: Built-in FastAPI UI at `/` and `/web` for episode control and response inspection
- **Comprehensive Benchmarking**: Automated scoring suite for all tasks

Each task has a deterministic grader with score in [0.0, 1.0].
Grader logic lives in env/grader.py and scores:
- fix correctness
- evidence coverage
- belief alignment
- mitigation timing
- revenue control and efficiency
- anti-gaming discipline (repetition, premature fixes, invalid fixes, excessive waiting)

Task-specific scoring component weights are explicit and deterministic to support reproducible evaluation.

## Reward Function

Step rewards provide dense trajectory feedback (not sparse binary only):
- positive reward for first-time evidence gathering
- positive reward for belief updates aligned with true world
- strong reward for correct fix, penalty for wrong/risky fix
- mitigation reward when used appropriately
- per-step time/revenue penalty to discourage stalling
- extra penalties for repetitive action spam and premature fix attempts

Hard tasks also use confidence gates: a fix can remain provisional until evidence and coordination requirements are met.

This reward design supports partial progress and discourages destructive behavior.

## Design Decisions That Matter

1. Stateful core API, stateless demo path
- `/reset`, `/step`, and `/state` share a single active environment instance so multi-step behavior is realistic and path-dependent.
- `/quick/demo` intentionally runs in an isolated env instance so reviewers can always reproduce a known walkthrough without mutating live session state.

2. Confidence gates are task-specific, not global
- Hard tasks enforce different completion gates (`required_evidence`, `required_belief_updates`, and optional mitigation-before-fix).
- This prevents one brittle policy from overfitting all tasks and creates meaningful differences between incident archetypes.

3. Belief updates are first-class actions
- The agent is rewarded for calibrated belief shaping, not just final fix selection.
- This allows partial credit for disciplined diagnosis and discourages shortcut policies that jump directly to fixes.

4. Anti-gaming is explicit in both reward and grader
- Repetition spam, premature fixes, invalid fixes, and over-waiting are penalized.
- The grader and dense reward both encode this, so exploit strategies lose score even when they occasionally hit a correct fix.

5. Browser UX and evaluator UX are separated cleanly
- Root Space UI supports manual interactive play.
- API remains strict and validator-compatible for automated checks.

## Agent Operating Strategy

A strong policy should follow a disciplined incident loop instead of single-shot fixing.

1. Triage phase (steps 1-2)
- Call `check_metrics` and `check_logs` early.
- Use `probe` when uncertainty remains between worlds with similar symptoms.

2. Hypothesis phase (next step)
- Call `update_belief` with a normalized distribution over candidate worlds.
- Avoid degenerate beliefs (all mass on one world) until evidence supports it.

3. Stabilization phase (hard tasks)
- If mitigation gate exists, call `safe_mitigation` before final fix commitment.
- This is critical for `revenue_tradeoff`, where mitigation timing is part of correctness.

4. Fix phase
- Use `commit_fix` only when evidence and belief-update gates are satisfied.
- If `requires_fix_confirmation=true`, continue evidence/belief actions before retrying final confirmation.

5. Exit discipline
- On `false_alarm`, high-confidence no-incident paths should prefer `wait` over unnecessary fixes.
- Avoid repeated same-action loops; they degrade anti-gaming components and overall score.

In short: diagnose -> calibrate -> mitigate (if needed) -> fix -> confirm.

## Environment Variables (Submission Requirements)

Define these before running inference:
- API_BASE_URL: API endpoint used by the OpenAI client (LLM endpoint)
- MODEL_NAME: model identifier
- HF_TOKEN: Hugging Face / API key
- LOCAL_IMAGE_NAME: optional local image name (kept for compatibility)
- REQUIRE_LLM: set to 1 to fail fast when no API key is available
- RESET_SEED: optional deterministic episode seed passed to /reset
- BASELINE_RESULTS_PATH: output path for structured baseline JSON (default: baseline_results.json)

Also set this for local env execution:
- ENV_BASE_URL: environment API base URL (default: http://localhost:7860)

The inference script uses the OpenAI Python client for all model calls (`from openai import OpenAI`) and reads the required variables above.
It follows the sample submission convention by defaulting only API_BASE_URL and MODEL_NAME, while keeping additional RealityOps runtime variables optional for local execution.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run Locally

```bash
uvicorn server.app:app --host 0.0.0.0 --port 7860
```

```bash
curl -X POST localhost:7860/reset -H 'content-type: application/json' -d '{}'
```

## Baseline Inference

The required inference entrypoint is at project root: inference.py.
It emits strict [START], [STEP], [END] lines and evaluates all tasks.

STDOUT contract (strict):
- [START] task=<task_name> env=<benchmark> model=<model_name>
- [STEP] step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
- [END] success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>

Formatting rules implemented:
- one START per episode, one STEP per step, one END per episode
- reward and rewards formatted to two decimals
- lowercase booleans for done/success
- error emitted as null when absent

```bash
python inference.py
```

Baseline scores from a deterministic local run (2026-04-08, RESET_SEED=9001):
- false_alarm: 0.923333
- ambiguous_root: 0.857791
- revenue_tradeoff: 0.755160
- cascading_failure: 0.886100
- multi_incident: 0.588333
- security_breach: 0.887500
- resource_exhaustion: 0.856071
- mean: 0.822041

Baseline artifacts committed in repo:
- baseline_output.txt (raw START/STEP/END transcript)
- baseline_results.json (timestamped structured report with per-task durations)

### Baseline Report (Consolidated)

#### Run Metadata

- Execution timestamp (UTC): 2026-04-08T17:30:03.174037+00:00
- Benchmark: realityops_arena
- Env URL: http://localhost:7860
- Policy mode: heuristic
- Model configured: Qwen/Qwen2.5-72B-Instruct
- Reset seed: 9001
- Source artifacts:
	- baseline_results.json
	- baseline_output.txt

#### Summary

- Episodes executed: 7/7 tasks
- Inference failures: 0/7
- Overall mean score: 0.822041
- Baseline type: HEURISTIC BASELINE (not LLM-backed in this run)

#### Difficulty Averages

- easy average: 0.923333
- medium average: 0.856931
- hard average: 0.842920
- ultra-hard average: 0.588333

#### Per-Task Results

| Task | Difficulty | Score | Steps | Duration (s) | Success |
|---|---|---:|---:|---:|---|
| false_alarm | easy | 0.923333 | 4 | 0.093394 | true |
| ambiguous_root | medium | 0.857791 | 5 | 0.041382 | true |
| revenue_tradeoff | hard | 0.755160 | 6 | 0.044195 | true |
| cascading_failure | hard | 0.886100 | 6 | 0.046797 | true |
| multi_incident | ultra-hard | 0.588333 | 8 | 0.049852 | true |
| security_breach | hard | 0.887500 | 6 | 0.048777 | true |
| resource_exhaustion | medium | 0.856071 | 5 | 0.047399 | true |

All per-task runtimes are well below the submission target of < 2 minutes.

#### Scenario Breakdown

- R001 false_alarm: 0.923333
- R002 ambiguous_root: 0.857791
- R003 revenue_tradeoff: 0.755160
- R004 cascading_failure: 0.886100
- R005 multi_incident: 0.588333
- R006 security_breach: 0.887500
- R007 resource_exhaustion: 0.856071

#### Multi-Model Validation Status

- Prepared script: benchmark.py
- Recommended command:
	python benchmark.py --require-llm --models Qwen/Qwen2.5-72B-Instruct meta-llama/Llama-3.1-70B-Instruct mistralai/Mistral-7B-Instruct-v0.3
- Current blocker in this local run: no active LLM credentials were provided, so only heuristic baseline was executed.

### Grader Walkthrough (Consolidated)

#### Task: cascading_failure

This walkthrough demonstrates how grading accumulates for a realistic hard-task trajectory where the agent gathers evidence, updates beliefs twice, and then applies the correct fix.

#### Scenario

- Active world: auth_expiry
- Required gates:
	- required_evidence >= 3
	- required_belief_updates >= 2
- Correct fix: refresh_token

#### Example Episode

- Step 1: check_logs
	- Evidence coverage increases.
	- Reward signal favors investigation.
	- No completion yet.
- Step 2: probe
	- Probe evidence and hint quality improve.
	- Revenue continues to accumulate each step.
- Step 3: check_metrics
	- Third evidence source reached.
	- Evidence gate is now satisfiable.
- Step 4: update_belief
	- First belief update recorded.
	- Belief alignment contributes to reward and grader components.
	- Belief gate still not satisfied.
- Step 5: update_belief
	- Second belief update recorded.
	- Belief gate becomes satisfied.
- Step 6: commit_fix(refresh_token)
	- Correct fix chosen.
	- With both confidence gates satisfied, episode can terminate.
	- Final score includes weighted components:
		- correct_fix: 0.37
		- coordination (belief updates): 0.25
		- evidence: 0.20
		- revenue_control: 0.13
		- anti_gaming: 0.05

#### Gate Violations and Penalties

- Evidence/belief gate violation on commit_fix:
	- Environment keeps episode open (done=false).
	- Runtime reward applies premature_fix_penalty = -0.20.
	- requires_fix_confirmation is set until gates are satisfied.
- Mitigation-before-fix gate violation (revenue_tradeoff, security_breach):
	- Episode does not complete on fix alone.
	- Grader component mitigation_before_fix remains 0.0, reducing final score by its full weight for that task.
- Repetition and stalling:
	- Runtime penalties and grader anti-gaming both reduce final score.

Note: if HF_TOKEN is not set or the model endpoint is unavailable, the script falls back to a deterministic heuristic policy while preserving the exact START/STEP/END output contract. For strict model-only runs, set REQUIRE_LLM=1.

## Docker

```bash
docker build -t realityops .
docker run --rm -p 7860:7860 realityops
```

## Validation

```bash
openenv validate
```

Optional pre-submission shell validator (from assignment):
- run the provided validate-submission.sh against your HF Space URL.
- script checks exactly: (1) POST /reset reachability, (2) docker build success, (3) openenv validate success.

```bash
PATH="/home/user/Desktop/RealityOps/.venv/bin:$PATH" ./validate-submission.sh https://thetallinnov8r-realityops.hf.space .

```

## Pre-Submission Checklist

- HF Space deploys and POST /reset returns HTTP 200
- openenv validate passes
- docker build succeeds from submitted repo
- inference.py runs end-to-end and prints START/STEP/END logs
- at least 3 tasks are present with deterministic graders and scores in [0.0, 1.0]
- API_BASE_URL, MODEL_NAME, HF_TOKEN are set in environment configuration

## Infra Expectations

- inference runtime target: under 20 minutes
- baseline designed for modest hardware (2 vCPU, 8 GB RAM)


## Project Structure

```text
env/
	core.py
	grader.py
	models.py
	tasks.py
	worlds.py
server/
	app.py
inference.py
openenv.yaml
Dockerfile
```