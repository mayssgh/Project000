"""
Computes cost per 1k requests for each model from the real usage numbers
recorded during src/run.py, using pricing from config.yaml.

For the two API models: cost is driven by input/output token pricing.
For the local model: cost is driven by amortized hardware cost per hour
and observed tokens/sec (i.e. how many requests/hour the hardware can do).

Also reports the traffic volume at which the API and self-hosted model
break even, and cost projected at 100x today's assumed traffic (which,
for a per-request cost, is just the same $/1k requests figure restated --
see the note printed at the end).

Usage:
    python src/cost.py
"""
import csv
import json
import os
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
CONFIG_PATH = os.path.join(ROOT, "config.yaml")
RESULTS_DIR = os.path.join(ROOT, "results")


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def cost_api_model(model_key: str, model_cfg: dict):
    path = os.path.join(RESULTS_DIR, f"scored_{model_key}.csv")
    if not os.path.exists(path):
        return None
    total_in, total_out, n = 0, 0, 0
    with open(path) as f:
        for row in csv.DictReader(f):
            if row["input_tokens"] and row["output_tokens"]:
                total_in += int(row["input_tokens"])
                total_out += int(row["output_tokens"])
                n += 1
    if n == 0:
        return None
    avg_in = total_in / n
    avg_out = total_out / n
    cost_per_request = (
        avg_in / 1_000_000 * model_cfg["price_per_m_input"]
        + avg_out / 1_000_000 * model_cfg["price_per_m_output"]
    )
    return {
        "model": model_key,
        "avg_input_tokens": round(avg_in, 1),
        "avg_output_tokens": round(avg_out, 1),
        "cost_per_1k_requests_usd": round(cost_per_request * 1000, 4),
    }


def cost_local_model(model_key: str, model_cfg: dict, hw_cfg: dict):
    path = os.path.join(RESULTS_DIR, f"scored_{model_key}.csv")
    if not os.path.exists(path):
        return None
    latencies_s, n = [], 0
    with open(path) as f:
        for row in csv.DictReader(f):
            latencies_s.append(float(row["latency_ms"]) / 1000)
            n += 1
    if n == 0:
        return None
    avg_latency_s = sum(latencies_s) / n
    requests_per_hour = 3600 / avg_latency_s if avg_latency_s > 0 else 0
    hourly_cost = hw_cfg.get("hourly_cost_usd", 0) or 0
    cost_per_request = (hourly_cost / requests_per_hour) if requests_per_hour > 0 else 0
    return {
        "model": model_key,
        "avg_latency_s": round(avg_latency_s, 3),
        "requests_per_hour": round(requests_per_hour, 1),
        "hardware": hw_cfg.get("description", "unspecified"),
        "hourly_cost_usd": hourly_cost,
        "cost_per_1k_requests_usd": round(cost_per_request * 1000, 4),
        "note": (
            "hourly_cost_usd is 0 in config.yaml -> cost is $0 (you already own the hardware). "
            "Set an amortized $/hour if you want a nonzero comparison, or report tokens/sec instead."
            if hourly_cost == 0 else ""
        ),
    }


def find_breakeven(api_cost_per_1k, local_cost_per_1k, local_fixed_hourly):
    """
    If local has a real hourly cost (fixed) and near-zero marginal cost per
    request, while API is pure per-request cost, breakeven volume (requests)
    solves: api_cost_per_req * N == local_fixed_hourly * hours_needed.
    Simplify: compare cost at N requests for both, assuming local can be run
    continuously and you pay for the wall-clock hours actually used.
    Here we just solve for N where API cumulative cost == local cumulative
    cost, treating local's cost as (hourly_cost * hours_to_process_N).
    """
    if api_cost_per_1k is None or local_cost_per_1k is None:
        return None
    if local_fixed_hourly == 0:
        return "local is $0 marginal cost (owned hardware) -> local is always cheaper past request 1"
    # cost_per_request_api * N = cost_per_request_local * N is trivial if both
    # are linear in N (which they are here) -- so breakeven is about FIXED
    # costs you haven't modeled (e.g. buying the GPU). Flag this honestly:
    return (
        "Both costs above are linear per-request, so there's no crossover volume "
        "from these numbers alone -- the real breakeven depends on the fixed cost "
        "of acquiring the hardware (not modeled here). Add that as a one-time cost "
        "amortized over your expected request volume to find it."
    )


def main():
    config = load_config()
    results = []

    for key in ["top_api", "cheap_api"]:
        r = cost_api_model(key, config["models"][key])
        if r:
            results.append(r)
            print(r)

    local_r = cost_local_model("local_oss", config["models"]["local_oss"], config["local_hardware"])
    if local_r:
        results.append(local_r)
        print(local_r)

    out_path = os.path.join(RESULTS_DIR, "cost_summary.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote {out_path}")

    # 100x traffic note
    print(
        "\nNote on 100x traffic: since cost_per_1k_requests is already a "
        "per-request rate, cost at 100x volume = cost_per_1k_requests * 100 "
        "(for API models). For the local model, check whether one machine's "
        "requests_per_hour above can actually sustain 100x your assumed "
        "request rate -- if not, you'd need N machines, which changes hourly_cost_usd."
    )

    api_cost = next((r["cost_per_1k_requests_usd"] for r in results if r["model"] == "top_api"), None)
    local_cost = next((r["cost_per_1k_requests_usd"] for r in results if r["model"] == "local_oss"), None)
    local_hourly = config["local_hardware"].get("hourly_cost_usd", 0)
    breakeven_note = find_breakeven(api_cost, local_cost, local_hourly)
    if breakeven_note:
        print(f"\nBreakeven note: {breakeven_note}")


if __name__ == "__main__":
    main()
