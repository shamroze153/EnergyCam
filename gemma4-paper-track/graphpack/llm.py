"""Minimal OpenAI-compatible chat client (vLLM `serve`, Google AI Studio, ...).

Configured with environment variables so the same code runs against a local
vLLM server in a Kaggle notebook or a hosted Gemma 4 endpoint while iterating:
  LLM_BASE_URL  e.g. http://localhost:8000/v1
                or https://generativelanguage.googleapis.com/v1beta/openai
  LLM_API_KEY   "EMPTY" for vLLM
  LLM_MODEL     the served model name, e.g. google/gemma-4-e4b-it
  LLM_EXTRA_BODY optional JSON merged into each request, e.g.
                '{"chat_template_kwargs": {"enable_thinking": false}}' for vLLM
"""
import json
import os
import re
import time
import urllib.error
import urllib.request


class ChatLLM:
    def __init__(self, base_url=None, api_key=None, model=None, temperature=0.0,
                 max_tokens=1024, timeout=600, retries=5):
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL", "http://localhost:8000/v1")).rstrip("/")
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "EMPTY")
        self.model = model or os.environ.get("LLM_MODEL", "google/gemma-4-e4b-it")
        self.temperature, self.max_tokens = temperature, max_tokens
        self.timeout, self.retries = timeout, retries

    def chat(self, messages):
        """Return (text, usage dict with prompt_tokens / completion_tokens)."""
        body = json.dumps({"model": self.model, "messages": messages,
                           "temperature": self.temperature, "max_tokens": self.max_tokens,
                           **json.loads(os.environ.get("LLM_EXTRA_BODY") or "{}")}).encode()
        req = urllib.request.Request(f"{self.base_url}/chat/completions", data=body, headers={
            "Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"})
        delay = 2
        for attempt in range(self.retries):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    out = json.loads(resp.read())
                text = out["choices"][0]["message"].get("content") or ""
                return text, out.get("usage", {}) or {}
            except urllib.error.HTTPError as e:
                # 429/5xx are worth retrying (free API tiers rate-limit hard)
                if e.code not in (429, 500, 502, 503, 504) or attempt == self.retries - 1:
                    raise RuntimeError(f"LLM HTTP {e.code}: {e.read()[:500]!r}") from e
            except (urllib.error.URLError, TimeoutError):
                if attempt == self.retries - 1:
                    raise
            time.sleep(delay)
            delay *= 2


class ScriptedLLM:
    """Replays fixed replies; used by the tests and for dry runs."""

    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def chat(self, messages):
        self.calls.append([dict(m) for m in messages])  # the agent keeps appending
        text = self.replies.pop(0) if self.replies else '{"locations": []}'
        return text, {"prompt_tokens": sum(len(m["content"]) for m in messages) // 4,
                      "completion_tokens": len(text) // 4}


def parse_json(text):
    """First JSON object in a model reply (tolerates ```json fences and chatter)."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    text = re.sub(r"<\|channel>.*?<channel\|>", "", text, flags=re.S)  # Gemma 4 thought channel
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    candidates = [fence.group(1)] if fence else []
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[start:i + 1])
                    break
        start = text.find("{", start + 1)
    for c in candidates:
        try:
            return json.loads(c)
        except json.JSONDecodeError:
            continue
    return None
