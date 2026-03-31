"""
Unified AI interface.
Supports: Ollama (local), Anthropic, Groq, OpenAI, DeepSeek, Gemini.
"""

import json
import os
import time
from typing import List, Optional

DEFAULT_OLLAMA_URL      = "http://localhost:11434/v1/chat/completions"
DEFAULT_OLLAMA_TAGS     = "http://localhost:11434/api/tags"
DEFAULT_OLLAMA_GENERATE = "http://localhost:11434/api/generate"

PROVIDER_DELAYS = {
    "anthropic": 1.0, "groq": 2.5, "openai": 1.0,
    "deepseek":  1.0, "gemini": 7.0, "ollama": 0.0,
}

OLLAMA_MODEL_PRIORITY = [
    ("qwen2.5-coder:7b",  5,  "Best speed/quality (~5GB)"),
    ("qwen3:8b",          5,  "Excellent reasoning (~5GB)"),
    ("qwen2.5-coder:14b", 10, "Higher quality (~10GB)"),
    ("codellama:7b",      5,  "Meta code model 7b"),
    ("llama3.1:8b",       5,  "Good all-around 8b"),
    ("mistral:7b",        5,  "Mistral 7b"),
    ("phi3.5:3.8b",       3,  "Phi-3.5 mini"),
    ("gemma3:4b",         3,  "Gemma 3 4b"),
]

_OLLAMA_MODELS_CACHE: Optional[List[str]] = None
_DETECTED_MODEL: Optional[str] = None


class AIConfig:
    def __init__(self, api_key="", provider="", model="", mode="", ollama_url=""):
        self.api_key    = api_key  or os.environ.get("AI_API_KEY", "")
        self.provider   = provider or os.environ.get("AI_PROVIDER", "")
        self.model      = model    or os.environ.get("AI_MODEL", "")
        self.mode       = mode     or os.environ.get("AI_MODE", "")
        self.ollama_url = ollama_url or DEFAULT_OLLAMA_URL

        if not self.provider:
            self.provider = _detect_provider(self.api_key)
        if self.mode == "local":
            self.provider = "ollama"
        if self.provider == "ollama" and not self.api_key:
            self.api_key = "ollama"

    @property
    def use_ai(self):
        return bool(self.api_key) or self.provider == "ollama"

    @property
    def delay(self):
        return PROVIDER_DELAYS.get(self.provider, 2.0)

    def resolved_model(self):
        if self.model:
            return self.model
        if self.provider == "ollama":
            return detect_best_ollama_model()
        models = {
            "anthropic": "claude-sonnet-4-5",
            "groq":      "llama-3.3-70b-versatile",
            "openai":    "gpt-4o-mini",
            "deepseek":  "deepseek-chat",
            "gemini":    "gemini-2.0-flash",
        }
        return models.get(self.provider, "unknown")


def _detect_provider(key):
    if not key or key == "ollama": return "ollama"
    if key.startswith("sk-ant-"):  return "anthropic"
    if key.startswith("gsk_"):     return "groq"
    if key.startswith("AIza"):     return "gemini"
    if key.startswith("sk-"):      return "openai"
    # Do NOT silently fall back — warn the user so they can set --provider
    print(
        "  [WARN] API key prefix not recognised. "
        "Set --provider explicitly (groq/openai/anthropic/gemini/deepseek/ollama). "
        "Defaulting to 'groq' — authentication will likely fail."
    )
    return "groq"


def get_ollama_models():
    global _OLLAMA_MODELS_CACHE
    if _OLLAMA_MODELS_CACHE is not None:
        return _OLLAMA_MODELS_CACHE
    import urllib.request
    try:
        with urllib.request.urlopen(DEFAULT_OLLAMA_TAGS, timeout=5) as r:
            data = json.loads(r.read())
            _OLLAMA_MODELS_CACHE = [m["name"] for m in data.get("models", [])]
    except Exception:
        _OLLAMA_MODELS_CACHE = []
    return _OLLAMA_MODELS_CACHE


def detect_best_ollama_model(preferred=""):
    global _DETECTED_MODEL
    if _DETECTED_MODEL:
        return _DETECTED_MODEL
    available   = get_ollama_models()
    avail_lower = [m.lower() for m in available]
    if preferred and preferred.lower() in avail_lower:
        _DETECTED_MODEL = available[avail_lower.index(preferred.lower())]
        return _DETECTED_MODEL
    if not available:
        _DETECTED_MODEL = "qwen2.5-coder:7b"
        return _DETECTED_MODEL
    for name, _, desc in OLLAMA_MODEL_PRIORITY:
        if name.lower() in avail_lower:
            _DETECTED_MODEL = available[avail_lower.index(name.lower())]
            print("  Auto-selected: {}  ({})".format(_DETECTED_MODEL, desc))
            return _DETECTED_MODEL
    _DETECTED_MODEL = available[0]
    return _DETECTED_MODEL


def _http_post(url, headers, payload, timeout=120):
    import urllib.request
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _call_ollama(model, messages, max_tokens, timeout=300):
    """
    Call Ollama using /api/generate (more stable than /v1/chat).
    Disables qwen3 thinking mode to prevent HTTP 500 errors.
    Falls back to /v1/chat if /api/generate fails.
    """
    import urllib.error
    import urllib.request

    # Build prompt from messages
    system_text = ""
    user_parts  = []
    for msg in messages:
        if msg["role"] == "system":
            system_text = msg["content"]
        elif msg["role"] == "user":
            user_parts.append(msg["content"])
    prompt = "\n\n".join(user_parts)

    # Strategy 1: /api/generate
    payload = {
        "model":  model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.1,
            "num_ctx":     4096,
        },
    }
    if system_text:
        payload["system"] = system_text
    # Disable qwen3 extended thinking (causes HTTP 500)
    if "qwen3" in model.lower():
        payload["think"] = False

    try:
        data = json.dumps(payload).encode()
        req  = urllib.request.Request(
            DEFAULT_OLLAMA_GENERATE,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            result = json.loads(r.read())
            return result.get("response", "").strip()
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()[:100]
        except Exception:
            pass
        print("    /api/generate HTTP {} -- trying /v1/chat fallback...".format(e.code))
    except Exception as ex:
        print("    /api/generate error: {} -- trying /v1/chat...".format(str(ex)[:60]))

    # Strategy 2: /v1/chat/completions fallback
    payload2 = {
        "model":       model,
        "max_tokens":  max_tokens,
        "messages":    messages,
        "temperature": 0.1,
        "stream":      False,
    }
    if "qwen3" in model.lower():
        payload2["options"] = {"num_ctx": 4096}

    try:
        data = json.dumps(payload2).encode()
        req  = urllib.request.Request(
            DEFAULT_OLLAMA_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            result = json.loads(r.read())
            return result["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()[:100]
        except Exception:
            pass
        return "[AI failed: HTTP {} {}]".format(e.code, body)
    except Exception as ex:
        return "[AI failed: {}]".format(str(ex)[:100])


def _openai_compat(url, key, model, messages, max_tokens, timeout=120):
    import urllib.error
    headers = {"Content-Type": "application/json"}
    if key and key != "ollama":
        headers["Authorization"] = "Bearer " + key
    for attempt in range(4):
        try:
            r = _http_post(
                url, headers,
                {"model": model, "max_tokens": max_tokens,
                 "messages": messages, "temperature": 0.1},
                timeout,
            )
            return r["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 20 * (attempt + 1)
                print("    Rate limited -- retry {}/4 in {}s...".format(attempt + 1, wait))
                time.sleep(wait)
            else:
                body = ""
                try:
                    body = e.read().decode()[:100]
                except Exception:
                    pass
                return "[AI failed: HTTP {} {}]".format(e.code, body)
        except Exception as ex:
            if "timed out" in str(ex).lower() and attempt < 3:
                print("    Timeout -- retry {}/4...".format(attempt + 1))
                continue
            return "[AI failed: {}]".format(str(ex)[:100])
    return "[AI failed: exhausted retries]"


def call_ai(prompt, config, system="", max_tokens=1200):
    """Call the configured AI provider. Returns the response string."""
    prov  = config.provider
    key   = config.api_key
    model = config.resolved_model()

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        if prov == "ollama":
            return _call_ollama(model, messages, max_tokens)

        if prov == "anthropic":
            payload = {
                "model":      model,
                "max_tokens": max_tokens,
                "messages":   [{"role": "user", "content": prompt}],
            }
            if system:
                payload["system"] = system
            r = _http_post(
                "https://api.anthropic.com/v1/messages",
                {"Content-Type": "application/json",
                 "x-api-key": key,
                 "anthropic-version": "2023-06-01"},
                payload,
            )
            return r["content"][0]["text"].strip()

        if prov == "groq":
            return _openai_compat(
                "https://api.groq.com/openai/v1/chat/completions",
                key, "llama-3.3-70b-versatile", messages, max_tokens,
            )

        if prov == "openai":
            return _openai_compat(
                "https://api.openai.com/v1/chat/completions",
                key, "gpt-4o-mini", messages, max_tokens,
            )

        if prov == "deepseek":
            return _openai_compat(
                "https://api.deepseek.com/chat/completions",
                key, "deepseek-chat", messages, max_tokens,
            )

        if prov == "gemini":
            import urllib.error
            parts = []
            if system:
                parts.append({"text": "[System]:\n" + system + "\n\n"})
            parts.append({"text": prompt})
            # API key sent as a header to avoid leaking it in server/proxy logs
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                "gemini-2.0-flash:generateContent"
            )
            for attempt in range(10):
                try:
                    r = _http_post(
                        url,
                        {"Content-Type": "application/json", "x-goog-api-key": key},
                        {"contents": [{"parts": parts}],
                         "generationConfig": {"maxOutputTokens": max_tokens,
                                              "temperature": 0.1}},
                    )
                    return r["candidates"][0]["content"]["parts"][0]["text"].strip()
                except urllib.error.HTTPError as e:
                    if e.code == 429:
                        wait = min(30 * (attempt + 1), 120)
                        print("    Gemini 429 -- retry {}/10 in {}s...".format(attempt + 1, wait))
                        time.sleep(wait)
                    else:
                        raise
            return "[AI failed: Gemini quota exhausted]"

        return "[AI failed: unknown provider {}]".format(prov)

    except Exception as ex:
        return "[AI failed: {}]".format(str(ex)[:100])