"""
Runs data/items.jsonl through a single configured model (one of
top_api / cheap_api / local_oss from config.yaml) and writes
results/raw_<label>.jsonl with the raw output, latency, and token usage
(where available) for every item.

Usage:
    python src/run.py --model top_api
    python src/run.py --model cheap_api
    python src/run.py --model local_oss

Requires ANTHROPIC_API_KEY in the environment for the two API models.
For local_oss, requires Ollama running (`ollama serve`) with the model
already pulled (`ollama pull qwen2.5:3b` or whatever config.yaml names).
"""
import argparse
import json
import os
import time
import sys

import yaml
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
ITEMS_PATH = os.path.join(ROOT, "data", "items.jsonl")
PROMPT_PATH = os.path.join(ROOT, "prompts", "text_to_sql.txt")
CONFIG_PATH = os.path.join(ROOT, "config.yaml")
RESULTS_DIR = os.path.join(ROOT, "results")


def load_items():
    items = []
    with open(ITEMS_PATH) as f:
        for line in f:
            items.append(json.loads(line))
    return items


def load_prompt_template():
    with open(PROMPT_PATH) as f:
        return f.read()


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def clean_sql(text: str) -> str:
    """Strip markdown fences / stray prose the model might add despite instructions."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        # drop a leading language tag like 'sql\n'
        if "\n" in text:
            first, rest = text.split("\n", 1)
            if first.strip().lower() in ("sql", "sqlite"):
                text = rest
    return text.strip()


def call_anthropic(model_id: str, prompt: str, temperature: float, max_tokens: int):
    import anthropic
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    t0 = time.perf_counter()
    resp = client.messages.create(
        model=model_id,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
    )
    latency_ms = (time.perf_counter() - t0) * 1000
    text = "".join(b.text for b in resp.content if b.type == "text")
    return {
        "raw_output": text,
        "latency_ms": latency_ms,
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
        "error": None,
    }


def call_ollama(model_id: str, host: str, prompt: str, temperature: float, max_tokens: int):
    t0 = time.perf_counter()
    try:
        resp = requests.post(
            f"{host}/api/generate",
            json={
                "model": model_id,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        latency_ms = (time.perf_counter() - t0) * 1000
        return {
            "raw_output": "",
            "latency_ms": latency_ms,
            "input_tokens": None,
            "output_tokens": None,
            "error": str(e),
        }
    latency_ms = (time.perf_counter() - t0) * 1000
    return {
        "raw_output": data.get("response", ""),
        "latency_ms": latency_ms,
        # Ollama returns eval_count (output tokens) and prompt_eval_count (input tokens)
        "input_tokens": data.get("prompt_eval_count"),
        "output_tokens": data.get("eval_count"),
        "error": None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, choices=["top_api", "cheap_api", "local_oss"])
    parser.add_argument("--limit", type=int, default=None, help="only run first N items (for a quick test)")
    args = parser.parse_args()

    config = load_config()
    model_cfg = config["models"][args.model]
    run_cfg = config["run"]
    items = load_items()
    if args.limit:
        items = items[: args.limit]
    template = load_prompt_template()

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_path = os.path.join(RESULTS_DIR, f"raw_{args.model}.jsonl")

    print(f"Running {len(items)} items against {model_cfg['label']} ({model_cfg['provider']})")

    results = []
    for i, item in enumerate(items, start=1):
        prompt = template.format(question=item["question"])

        if model_cfg["provider"] == "anthropic":
            out = call_anthropic(
                model_cfg["model_id"], prompt,
                run_cfg["temperature"], run_cfg["max_tokens"],
            )
        elif model_cfg["provider"] == "ollama":
            out = call_ollama(
                model_cfg["model_id"], model_cfg["ollama_host"], prompt,
                run_cfg["temperature"], run_cfg["max_tokens"],
            )
        else:
            raise ValueError(f"Unknown provider {model_cfg['provider']}")

        out["id"] = item["id"]
        out["question"] = item["question"]
        out["gold_sql"] = item["gold_sql"]
        out["difficulty"] = item["difficulty"]
        out["model_label"] = model_cfg["label"]
        if out["error"] is None:
            out["predicted_sql"] = clean_sql(out["raw_output"])
        else:
            out["predicted_sql"] = ""

        results.append(out)
        status = "OK" if out["error"] is None else f"ERROR: {out['error']}"
        print(f"  [{i}/{len(items)}] item {item['id']} ({item['difficulty']}) - {status} - {out['latency_ms']:.0f}ms")

    with open(out_path, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    print(f"\nWrote {len(results)} results to {out_path}")


if __name__ == "__main__":
    main()
