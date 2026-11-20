"""Talk to an AI provider using only the standard library (no SDK needed)."""

import json
import urllib.error
import urllib.request

from . import config


class AIError(RuntimeError):
    pass


def _post(url, headers, payload, timeout=300):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        raise AIError(f"API returned HTTP {e.code}: {body}") from None
    except urllib.error.URLError as e:
        raise AIError(f"Could not reach the API: {e.reason}") from None


def complete(system, prompt, cfg=None):
    """Send one prompt, return the model's text reply."""
    cfg = cfg or config.load()
    key = config.get_api_key(cfg)
    provider = cfg["provider"]
    if not key and not (provider == "openai" and cfg.get("base_url")):
        raise AIError(
            "No API key found. Run:  worklog config set api_key YOUR_KEY\n"
            "or set the WORKLOG_API_KEY environment variable."
        )

    if provider == "anthropic":
        base = (cfg.get("base_url") or "https://api.anthropic.com").rstrip("/")
        data = _post(
            f"{base}/v1/messages",
            {"x-api-key": key, "anthropic-version": "2023-06-01"},
            {
                "model": cfg["model"],
                "max_tokens": int(cfg["max_tokens"]),
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
        text = "".join(parts).strip()
    elif provider == "openai":
        base = (cfg.get("base_url") or "https://api.openai.com/v1").rstrip("/")
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        data = _post(
            f"{base}/chat/completions",
            headers,
            {
                "model": cfg["model"],
                "max_tokens": int(cfg["max_tokens"]),
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        try:
            text = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError):
            raise AIError(f"Unexpected API response: {str(data)[:300]}") from None
    else:
        raise AIError(f"Unknown provider '{provider}'. Use 'anthropic' or 'openai'.")

    if not text:
        raise AIError("The API returned an empty response.")
    return text
