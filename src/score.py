"""
Scores a results/raw_<model>.jsonl file by executing both the predicted
and gold SQL against db/data.db and comparing the returned rows.

A predicted query is "correct" if its result set matches the gold result
set exactly as an unordered multiset of rows (values compared after
rounding floats to 4 decimals, so harmless float noise doesn't fail a
query). A SQL parse/exec error, empty predicted_sql, or timeout counts
as wrong -- never as skipped.

Usage:
    python src/score.py --model top_api
    python src/score.py --model cheap_api
    python src/score.py --model local_oss
    python src/score.py --all      # scores all three and writes summary.csv
"""
import argparse
import csv
import json
import os
import sqlite3
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
DB_PATH = os.path.join(ROOT, "db", "data.db")
RESULTS_DIR = os.path.join(ROOT, "results")
MODELS = ["top_api", "cheap_api", "local_oss"]

QUERY_TIMEOUT_SECONDS = 5


class Timeout(Exception):
    pass


def _normalize_rows(rows):
    out = []
    for row in rows:
        norm = tuple(
            round(v, 4) if isinstance(v, float) else v
            for v in row
        )
        out.append(norm)
    return sorted(out, key=lambda r: [str(x) for x in r])


def run_query(conn, sql, timeout=QUERY_TIMEOUT_SECONDS):
    """
    Cross-platform query timeout: SIGALRM only exists on Unix, so on Windows
    (and to be safe, everywhere) we use a threading.Timer that calls
    conn.interrupt() after `timeout` seconds. interrupt() causes the running
    query to raise sqlite3.OperationalError("interrupted") from inside
    cur.execute(), which we catch and treat as a timeout.
    """
    cur = conn.cursor()
    timer = threading.Timer(timeout, conn.interrupt)
    timer.start()
    try:
        cur.execute(sql)
        rows = cur.fetchall()
        return rows, None
    except sqlite3.OperationalError as e:
        if "interrupted" in str(e).lower():
            return None, "timeout"
        return None, f"sql_error: {e}"
    except sqlite3.Error as e:
        return None, f"sql_error: {e}"
    finally:
        timer.cancel()


def score_item(conn, predicted_sql, gold_sql):
    if not predicted_sql or not predicted_sql.strip():
        return False, "empty_prediction"

    pred_rows, pred_err = run_query(conn, predicted_sql)
    if pred_err:
        return False, pred_err

    gold_rows, gold_err = run_query(conn, gold_sql)
    if gold_err:
        # should not happen -- gold was pre-validated -- but guard anyway
        return False, f"gold_error: {gold_err}"

    correct = _normalize_rows(pred_rows) == _normalize_rows(gold_rows)
    return correct, None if correct else "mismatch"


def score_model(model_key: str):
    raw_path = os.path.join(RESULTS_DIR, f"raw_{model_key}.jsonl")
    if not os.path.exists(raw_path):
        print(f"Skipping {model_key}: {raw_path} not found (run src/run.py first)")
        return None

    conn = sqlite3.connect(DB_PATH)
    per_item = []
    with open(raw_path) as f:
        for line in f:
            r = json.loads(line)
            if r.get("error"):
                correct, reason = False, f"api_error: {r['error']}"
            else:
                correct, reason = score_item(conn, r["predicted_sql"], r["gold_sql"])
            per_item.append({
                "id": r["id"],
                "difficulty": r["difficulty"],
                "question": r["question"],
                "predicted_sql": r.get("predicted_sql", ""),
                "gold_sql": r["gold_sql"],
                "correct": correct,
                "fail_reason": reason or "",
                "latency_ms": r["latency_ms"],
                "input_tokens": r.get("input_tokens"),
                "output_tokens": r.get("output_tokens"),
            })
    conn.close()

    out_path = os.path.join(RESULTS_DIR, f"scored_{model_key}.csv")
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(per_item[0].keys()))
        writer.writeheader()
        writer.writerows(per_item)

    n = len(per_item)
    n_correct = sum(1 for r in per_item if r["correct"])
    print(f"{model_key}: {n_correct}/{n} correct -> wrote {out_path}")

    wrong = [r for r in per_item if not r["correct"]]
    print(f"  {len(wrong)} wrong. First 3 wrong examples:")
    for r in wrong[:3]:
        print(f"    id={r['id']} [{r['fail_reason']}] Q: {r['question'][:70]}")

    return per_item


def write_summary(all_results: dict):
    """all_results: {model_key: per_item list}"""
    summary_path = os.path.join(RESULTS_DIR, "summary.csv")
    rows = []
    for model_key, items in all_results.items():
        if not items:
            continue
        n = len(items)
        n_correct = sum(1 for r in items if r["correct"])
        latencies = sorted(r["latency_ms"] for r in items)
        p50 = latencies[int(0.50 * (n - 1))]
        p95 = latencies[int(0.95 * (n - 1))]
        rows.append({
            "model": model_key,
            "n_items": n,
            "n_correct": n_correct,
            "accuracy": round(n_correct / n, 3),
            "p50_latency_ms": round(p50, 1),
            "p95_latency_ms": round(p95, 1),
        })
    with open(summary_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["model", "n_items", "n_correct", "accuracy", "p50_latency_ms", "p95_latency_ms"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {summary_path}")
    for r in rows:
        print(f"  {r}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=MODELS)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    if args.all:
        all_results = {m: score_model(m) for m in MODELS}
        write_summary(all_results)
    elif args.model:
        score_model(args.model)
    else:
        parser.error("pass --model <name> or --all")


if __name__ == "__main__":
    main()