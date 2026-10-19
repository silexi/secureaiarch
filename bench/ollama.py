"""Minimal Ollama HTTP client (standard library only)."""
from __future__ import annotations

import json
import os
import time
import urllib.request

BASE = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
if not BASE.startswith("http"):
    BASE = "http://" + BASE


def _post(path: str, body: dict, timeout: int = 600) -> dict:
    req = urllib.request.Request(f"{BASE}{path}", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _get(path: str, timeout: int = 30) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=timeout) as r:
        return json.loads(r.read())


class Client:
    """Talks to a local Ollama server. `fmt` is passed through as Ollama's `format`
    (a JSON schema enables constrained decoding)."""

    def chat(self, model: str, messages: list[dict], temperature: float, fmt=None,
             num_predict: int = 400, seed: int | None = None, tools: list[dict] | None = None,
             top_logprobs: int = 0) -> dict:
        options = {"temperature": temperature, "num_predict": num_predict}
        if seed is not None:
            options["seed"] = seed
        body = {"model": model, "messages": messages, "stream": False, "options": options, "think": False}
        if fmt is not None:
            body["format"] = fmt
        if tools is not None:
            body["tools"] = tools
        if top_logprobs:
            body["logprobs"] = True
            body["top_logprobs"] = top_logprobs
        t0 = time.perf_counter()
        data = _post("/api/chat", body)
        message = data.get("message", {}) or {}
        return {
            "text": (message.get("content") or "").strip(),
            "tool_calls": [{"name": c.get("function", {}).get("name", ""), "arguments": c.get("function", {}).get("arguments") or {}}
                           for c in message.get("tool_calls") or []],
            "message": message,
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "output_tokens": data.get("eval_count", 0),
            "seconds": time.perf_counter() - t0,
            "logprobs": data.get("logprobs") or [],
        }

    def capabilities(self, model: str) -> list[str]:
        try:
            return _post("/api/show", {"model": model}, timeout=30).get("capabilities", [])
        except Exception:
            return []

    def embed(self, model: str, inputs: list[str]) -> list[list[float]]:
        out = []
        for i in range(0, len(inputs), 32):
            out.extend(_post("/api/embed", {"model": model, "input": inputs[i:i + 32]})["embeddings"])
        return out

    def version(self) -> str:
        try:
            return _get("/api/version").get("version", "")
        except Exception:
            return ""

    def model_info(self, model: str) -> dict:
        try:
            tags = _get("/api/tags").get("models", [])
        except Exception:
            tags = []
        for m in tags:
            if m.get("name") == model or m.get("model") == model:
                d = m.get("details", {})
                return {"digest": m.get("digest", "")[:12], "parameter_size": d.get("parameter_size", ""),
                        "quantization": d.get("quantization_level", ""), "family": d.get("family", "")}
        return {}
