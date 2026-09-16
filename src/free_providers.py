"""
free_providers.py

Drop this file into src/ (next to run.py). It gives you one function,
call_free_model(), that works for Groq, OpenRouter, and Gemini, since
all three expose an OpenAI-compatible /chat/completions endpoint.

Usage from run.py:

    from free_providers import call_free_model

    text, usage = call_free_model(
        provider="groq",                          # "groq" | "openrouter" | "gemini"
        model="llama-3.3-70b-versatile",
        prompt=full_prompt_string,
    )

Set your keys in .env (already done):
    GROQ_API_KEY=...
    OPENROUTER_API_KEY=...
    GEMINI_API_KEY=...
"""

import os
import time
import random
import requests
from dotenv import load_dotenv

load_dotenv()

PROVIDER_CONFIG = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "key_env": "GEMINI_API_KEY",
    },
}


RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def call_free_model(
    provider: str,
    model: str,
    prompt: str,
    temperature: float = 0.0,
    timeout: int = 60,
    max_retries: int = 4,
    base_delay: float = 2.0,
):
    """
    Calls a free-tier model via its OpenAI-compatible endpoint.

    Retries automatically on transient errors (429 rate limit, 500/502/503/504
    server-side issues) using exponential backoff with jitter: waits
    ~2s, 4s, 8s, 16s between attempts (capped), so a temporary "high demand"
    503 from Gemini (or a rate limit from Groq/OpenRouter) doesn't kill your
    whole run.py pass over 50 items.

    Returns:
        (text, usage_dict, latency_seconds)

    latency_seconds is the time for the successful call only (retries/waiting
    time is not included), so it stays comparable across providers/models.

    usage_dict has "prompt_tokens" / "completion_tokens" when the provider
    reports them (Groq and OpenRouter do; Gemini's OpenAI-compat layer may
    not always) — score.py / cost.py should handle usage_dict being partial
    or empty.

    Raises RuntimeError if every retry attempt fails.
    """
    if provider not in PROVIDER_CONFIG:
        raise ValueError(f"Unknown provider '{provider}'. Choose from: {list(PROVIDER_CONFIG)}")

    cfg = PROVIDER_CONFIG[provider]
    api_key = os.environ.get(cfg["key_env"])
    if not api_key:
        raise RuntimeError(
            f"Missing {cfg['key_env']} in your .env file. "
            f"Add a line like {cfg['key_env']}=your_key_here and try again."
        )

    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            start = time.time()
            resp = requests.post(
                f"{cfg['base_url']}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                },
                timeout=timeout,
            )
            latency = time.time() - start

            if resp.status_code == 200:
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                return text, usage, latency

            if resp.status_code in RETRYABLE_STATUS_CODES and attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 1)
                print(
                    f"[{provider}] {resp.status_code} (attempt {attempt}/{max_retries}), "
                    f"retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
                last_error = f"{resp.status_code}: {resp.text[:300]}"
                continue

            # Non-retryable status code (e.g. 401, 403, 404) — fail immediately.
            raise RuntimeError(f"{provider} API error {resp.status_code}: {resp.text[:500]}")

        except requests.exceptions.RequestException as e:
            # Network-level failure (timeout, connection reset, etc.) — also retryable.
            last_error = str(e)
            if attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 1)
                print(f"[{provider}] network error (attempt {attempt}/{max_retries}), retrying in {delay:.1f}s...")
                time.sleep(delay)
                continue

    raise RuntimeError(
        f"{provider} API failed after {max_retries} attempts. Last error: {last_error}"
    )


if __name__ == "__main__":
    # Quick manual smoke test: python free_providers.py
    # NOTE: Groq deprecated llama-3.3-70b-versatile / llama-3.1-8b-instant for
    # free & developer tier accounts on 2026-06-17. openai/gpt-oss-120b is
    # their current recommended replacement (strong reasoning + tool calling).
    # If any of these 404 again in the future, check console.groq.com/docs/models
    # or https://openrouter.ai/models?max_price=0 for current free model IDs.
    for provider, model in [
        ("groq", "openai/gpt-oss-120b"),
        ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"),
        ("gemini", "gemini-flash-latest"),
    ]:
        try:
            text, usage, latency = call_free_model(provider, model, "Say 'hello' and nothing else.")
            print(f"[{provider}] OK ({latency:.2f}s) -> {text.strip()[:80]}  usage={usage}")
        except Exception as e:
            print(f"[{provider}] FAILED: {e}")