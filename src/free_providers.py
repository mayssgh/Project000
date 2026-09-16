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


def call_free_model(provider: str, model: str, prompt: str, temperature: float = 0.0, timeout: int = 60):
    """
    Calls a free-tier model via its OpenAI-compatible endpoint.

    Returns:
        (text, usage_dict, latency_seconds)

    usage_dict has "prompt_tokens" / "completion_tokens" when the provider
    reports them (Groq and OpenRouter do; Gemini's OpenAI-compat layer may
    not always) — score.py / cost.py should handle usage_dict being partial
    or empty.
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

    if resp.status_code != 200:
        raise RuntimeError(f"{provider} API error {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})  # e.g. {"prompt_tokens": .., "completion_tokens": ..}

    return text, usage, latency


if __name__ == "__main__":
    # Quick manual smoke test: python free_providers.py
    for provider, model in [
        ("groq", "llama-3.3-70b-versatile"),
        ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"),
        ("gemini", "gemini-flash-latest"),
    ]:
        try:
            text, usage, latency = call_free_model(provider, model, "Say 'hello' and nothing else.")
            print(f"[{provider}] OK ({latency:.2f}s) -> {text.strip()[:80]}  usage={usage}")
        except Exception as e:
            print(f"[{provider}] FAILED: {e}")