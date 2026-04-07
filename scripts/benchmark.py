import subprocess
import json
import os
import sys

def run_inference(task, model="Qwen/Qwen2.5-72B-Instruct", max_steps=8):
    env = os.environ.copy()
    env.update({
        "MODEL_NAME": model,
        "TASK_NAME": task,
        "MAX_STEPS": str(max_steps),
        "API_BASE_URL": "https://router.huggingface.co/v1",  # Dummy, will fail but parse output
        "HF_TOKEN": "",
        "ENV_BASE_URL": "http://localhost:8002",
    })
    try:
        result = subprocess.run([sys.executable, "inference.py"], env=env, capture_output=True, text=True, timeout=60)
        # Parse [END] line for score
        for line in result.stdout.split('\n'):
            if line.startswith('[END]'):
                parts = line.split()
                steps = int(parts[2].split('=')[1].rstrip(','))
                score = float(parts[3].split('=')[1].rstrip(','))
                return {"score": score, "steps": steps, "success": score >= 0.45}
        return {"score": 0.0, "steps": 0, "success": False}
    except subprocess.TimeoutExpired:
        return {"score": 0.0, "steps": 0, "success": False, "error": "timeout"}
    except Exception as e:
        return {"score": 0.0, "steps": 0, "success": False, "error": str(e)}

def main():
    tasks = ["false_alarm", "ambiguous_root", "revenue_tradeoff", "cascading_failure", "multi_incident", "security_breach", "resource_exhaustion"]
    results = {}
    for task in tasks:
        print(f"Running {task}...")
        results[task] = run_inference(task)
    
    print(json.dumps(results, indent=2))
    
    # Summary
    avg_score = sum(r["score"] for r in results.values()) / len(results)
    success_rate = sum(1 for r in results.values() if r["success"]) / len(results)
    print(f"\nAverage Score: {avg_score:.3f}")
    print(f"Success Rate: {success_rate:.1%}")

if __name__ == "__main__":
    main()