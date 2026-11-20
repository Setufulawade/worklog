"""User configuration (AI provider, model, API key)."""

import json
import os
import stat

from .storage import config_dir

DEFAULTS = {
    "provider": "anthropic",  # "anthropic" or "openai" (any OpenAI-compatible API)
    "model": "claude-sonnet-5-5",
    "base_url": "",  # optional override, e.g. http://localhost:11434/v1 for Ollama
    "api_key": "",
    "max_tokens": 8000,
}

PROVIDER_DEFAULT_MODEL = {
    "anthropic": "claude-sonnet-5-5",
    "openai": "gpt-4o",
}

ENV_KEYS = {
    "anthropic": ["WORKLOG_API_KEY", "ANTHROPIC_API_KEY"],
    "openai": ["WORKLOG_API_KEY", "OPENAI_API_KEY"],
}


def config_path():
    return config_dir() / "config.json"


def load():
    cfg = dict(DEFAULTS)
    p = config_path()
    if p.exists():
        try:
            cfg.update(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    return cfg


def save(cfg):
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)  # 600: it may contain an API key


def get_api_key(cfg):
    for name in ENV_KEYS.get(cfg["provider"], ["WORKLOG_API_KEY"]):
        if os.environ.get(name):
            return os.environ[name]
    return cfg.get("api_key") or ""


def mask(key):
    if not key:
        return "(not set)"
    return key[:4] + "..." + key[-4:] if len(key) > 10 else "****"
