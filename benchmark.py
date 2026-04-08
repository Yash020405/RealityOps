import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


DEFAULT_MODELS = [
    "Qwen/Qwen2.5-72B-Instruct",
    "meta-llama/Llama-3.1-70B-Instruct",
    "mistralai/Mistral-7B-Instruct-v0.3",
]


def run_model_baseline(model: str, output_dir: Path, require_llm: bool, reset_seed: int | None) -> dict:
    model_slug = model.replace("/", "__")
    txt_path = output_dir / f"baseline_{model_slug}.txt"
    json_path = output_dir / f"baseline_{model_slug}.json"

    env = os.environ.copy()
    env["MODEL_NAME"] = model
    env["BASELINE_RESULTS_PATH"] = str(json_path)
    env["REQUIRE_LLM"] = "1" if require_llm else "0"
    if reset_seed is not None:
        env["RESET_SEED"] = str(reset_seed)

    cmd = [sys.executable, "inference.py"]
    with txt_path.open("w", encoding="utf-8") as outfile:
        proc = subprocess.run(cmd, env=env, stdout=outfile, stderr=subprocess.PIPE, text=True)

    summary = {
        "model": model,
        "exit_code": proc.returncode,
        "stdout_path": str(txt_path),
        "json_path": str(json_path),
    }
    if proc.returncode != 0:
        summary["error"] = (proc.stderr or "").strip()[:500]
        return summary

    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        summary["mean_score"] = payload.get("mean_score")
        summary["policy_mode"] = payload.get("policy_mode")
        summary["scores"] = payload.get("scores", {})
    except Exception as exc:
        summary["error"] = f"Failed to parse baseline JSON: {exc}"

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RealityOps baseline across multiple models.")
    parser.add_argument("--models", nargs="*", default=DEFAULT_MODELS, help="Model IDs to benchmark")
    parser.add_argument("--output-dir", default="benchmark_results", help="Output directory")
    parser.add_argument("--require-llm", action="store_true", help="Fail if model credentials are unavailable")
    parser.add_argument("--reset-seed", type=int, default=9001, help="Deterministic reset seed")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summaries = []
    for model in args.models:
        print(f"Running baseline for model: {model}")
        summaries.append(run_model_baseline(model, output_dir, args.require_llm, args.reset_seed))

    summary_path = output_dir / "benchmark_summary.json"
    summary_path.write_text(json.dumps(summaries, indent=2) + "\n", encoding="utf-8")

    print("\nBenchmark summary written to:", summary_path)
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()