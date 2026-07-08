"""
Unified interface ke berbagai LLM API. Semua return format sama:
{
  "content": "<text dari model, bisa kosong>",
  "tool_calls": [{"id": "...", "name": "...", "arguments": {...}}]
}
"""
import json
import time
import requests
import config


class BaseProvider:
    name = "base"

    def chat(self, messages, tools, on_token=None):
        raise NotImplementedError


CONTEXT_WINDOWS = {
    "llama-3.3-70b-versatile": 128_000,
    "claude-sonnet-4-6": 200_000,
    "gpt-4o-mini": 128_000,
    "mimo-v2.5": 128_000,
    "mimo": 128_000,
}

RETRYABLE_STATUS = {429, 500, 502, 503, 529}
MAX_RETRIES = 4
BASE_BACKOFF = 2


def _request_with_retry(method, url, **kwargs):
    last_exc = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = method(url, **kwargs)
        except requests.exceptions.RequestException as e:
            last_exc = e
            if attempt == MAX_RETRIES:
                raise
            time.sleep(BASE_BACKOFF * (2 ** attempt))
            continue

        if resp.status_code in RETRYABLE_STATUS and attempt < MAX_RETRIES:
            wait = BASE_BACKOFF * (2 ** attempt)
            retry_after = resp.headers.get("retry-after")
            if retry_after:
                try:
                    wait = max(wait, float(retry_after))
                except ValueError:
                    pass
            time.sleep(wait)
            continue

        return resp

    if last_exc:
        raise last_exc
    return resp


class OpenAICompatProvider(BaseProvider):
    def __init__(self, api_key, base_url, model, backup_keys=None):
        self.api_key = api_key
        self.backup_keys = backup_keys or []
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.context_window = CONTEXT_WINDOWS.get(model, 128_000)

    def _try_request(self, api_key, messages, tools, on_token=None, stream=False):
        """Kirim request dengan key tertentu."""
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": config.MAX_TOKENS,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if stream:
            payload["stream_options"] = {"include_usage": True}

        resp = _request_with_retry(
            requests.post,
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
            stream=stream,
        )
        resp.raise_for_status()

        if not stream:
            data = resp.json()
            msg = data["choices"][0]["message"]
            tool_calls = []
            for tc in msg.get("tool_calls") or []:
                tool_calls.append(
                    {
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "arguments": json.loads(tc["function"]["arguments"] or "{}"),
                    }
                )
            u = data.get("usage", {}) or {}
            usage = {
                "input": u.get("prompt_tokens", 0),
                "output": u.get("completion_tokens", 0),
                "total": u.get("total_tokens", 0),
            }
            return {
                "content": msg.get("content") or "",
                "tool_calls": tool_calls,
                "raw_message": msg,
                "usage": usage,
            }

        content = ""
        tool_calls_acc = {}
        usage = {"input": 0, "output": 0, "total": 0}

        for line in resp.iter_lines():
            if not line:
                continue
            line = line.decode("utf-8")
            if not line.startswith("data: "):
                continue
            payload_str = line[len("data: "):]
            if payload_str.strip() == "[DONE]":
                break
            try:
                chunk = json.loads(payload_str)
            except Exception:
                continue

            choice = (chunk.get("choices") or [{}])[0]
            delta = choice.get("delta", {})

            if delta.get("content"):
                piece = delta["content"]
                content += piece
                on_token(piece)

            for tc in delta.get("tool_calls") or []:
                idx = tc.get("index", 0)
                acc = tool_calls_acc.setdefault(idx, {"id": None, "name": "", "arguments": ""})
                if tc.get("id"):
                    acc["id"] = tc["id"]
                fn = tc.get("function") or {}
                if fn.get("name"):
                    acc["name"] += fn["name"]
                if fn.get("arguments"):
                    acc["arguments"] += fn["arguments"]

            u = chunk.get("usage")
            if u:
                usage = {
                    "input": u.get("prompt_tokens", 0),
                    "output": u.get("completion_tokens", 0),
                    "total": u.get("total_tokens", 0),
                }

        tool_calls = []
        for idx in sorted(tool_calls_acc):
            acc = tool_calls_acc[idx]
            try:
                args = json.loads(acc["arguments"] or "{}")
            except Exception:
                args = {}
            tool_calls.append({"id": acc["id"] or f"call_{idx}", "name": acc["name"], "arguments": args})

        return {"content": content, "tool_calls": tool_calls, "raw_message": None, "usage": usage}

    def _call_with_fallback(self, messages, tools, on_token=None):
        """Coba primary key, kalau 429 coba backup keys."""
        stream = on_token is not None
        keys_to_try = [self.api_key] + self.backup_keys
        last_error = None

        for i, key in enumerate(keys_to_try):
            try:
                resp = _request_with_retry(
                    requests.post,
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        **({"tools": tools, "tool_choice": "auto"} if tools else {}),
                        "max_tokens": config.MAX_TOKENS,
                        "stream": stream,
                        **({"stream_options": {"include_usage": True}} if stream else {}),
                    },
                    timeout=60,
                    stream=stream,
                )

                if resp.status_code == 429 and i < len(keys_to_try) - 1:
                    print(f"\n[switching API key {i+1}/{len(keys_to_try)} — primary limit hit]")
                    last_error = resp
                    continue

                resp.raise_for_status()

                if not stream:
                    data = resp.json()
                    msg = data["choices"][0]["message"]
                    tool_calls = []
                    for tc in msg.get("tool_calls") or []:
                        tool_calls.append({
                            "id": tc["id"],
                            "name": tc["function"]["name"],
                            "arguments": json.loads(tc["function"]["arguments"] or "{}"),
                        })
                    u = data.get("usage") or {}
                    usage = {
                        "input": u.get("prompt_tokens", 0),
                        "output": u.get("completion_tokens", 0),
                        "total": u.get("total_tokens", 0),
                    }
                    return {"content": msg.get("content") or "", "tool_calls": tool_calls, "raw_message": msg, "usage": usage}

                # Streaming
                content = ""
                tool_calls_acc = {}
                usage = {"input": 0, "output": 0, "total": 0}
                for line in resp.iter_lines():
                    if not line:
                        continue
                    line = line.decode("utf-8")
                    if not line.startswith("data: "):
                        continue
                    payload_str = line[len("data: "):]
                    if payload_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload_str)
                    except Exception:
                        continue
                    choice = (chunk.get("choices") or [{}])[0]
                    delta = choice.get("delta", {})
                    if delta.get("content"):
                        piece = delta["content"]
                        content += piece
                        on_token(piece)
                    for tc in delta.get("tool_calls") or []:
                        idx = tc.get("index", 0)
                        acc = tool_calls_acc.setdefault(idx, {"id": None, "name": "", "arguments": ""})
                        if tc.get("id"):
                            acc["id"] = tc["id"]
                        fn = tc.get("function") or {}
                        if fn.get("name"):
                            acc["name"] += fn["name"]
                        if fn.get("arguments"):
                            acc["arguments"] += fn["arguments"]
                    u = chunk.get("usage")
                    if u:
                        usage = {
                            "input": u.get("prompt_tokens", 0),
                            "output": u.get("completion_tokens", 0),
                            "total": u.get("total_tokens", 0),
                        }
                tool_calls = []
                for idx in sorted(tool_calls_acc):
                    acc = tool_calls_acc[idx]
                    try:
                        args = json.loads(acc["arguments"] or "{}")
                    except Exception:
                        args = {}
                    tool_calls.append({"id": acc["id"] or f"call_{idx}", "name": acc["name"], "arguments": args})
                return {"content": content, "tool_calls": tool_calls, "raw_message": None, "usage": usage}

            except requests.exceptions.HTTPError as e:
                if e.response and e.response.status_code == 429 and i < len(keys_to_try) - 1:
                    print(f"\n[switching API key {i+1}/{len(keys_to_try)} — rate limited]")
                    last_error = e
                    continue
                raise

        if last_error:
            raise last_error
        raise ValueError("All API keys exhausted")

    def chat(self, messages, tools, on_token=None):
        return self._call_with_fallback(messages, tools, on_token)


class ClaudeProvider(BaseProvider):
    name = "claude"

    def __init__(self, api_key, model="claude-sonnet-4-6"):
        self.api_key = api_key
        self.model = model
        self.context_window = CONTEXT_WINDOWS.get(model, 200_000)

    @staticmethod
    def _convert_tools(tools):
        converted = []
        for t in tools:
            fn = t["function"]
            converted.append(
                {
                    "name": fn["name"],
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
                }
            )
        return converted

    @staticmethod
    def _convert_messages(messages):
        system = ""
        out = []
        for m in messages:
            if m["role"] == "system":
                system += m["content"] + "\n"
            elif m["role"] == "tool":
                out.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m["tool_call_id"],
                                "content": m["content"],
                            }
                        ],
                    }
                )
            elif m["role"] == "assistant" and m.get("tool_calls"):
                blocks = []
                if m.get("content"):
                    blocks.append({"type": "text", "text": m["content"]})
                for tc in m["tool_calls"]:
                    args = tc["function"]["arguments"]
                    if isinstance(args, str):
                        args = json.loads(args or "{}")
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": tc["function"]["name"],
                            "input": args,
                        }
                    )
                out.append({"role": "assistant", "content": blocks})
            else:
                out.append({"role": m["role"], "content": m["content"]})
        return system.strip(), out

    def chat(self, messages, tools, on_token=None):
        system, conv = self._convert_messages(messages)
        stream = on_token is not None

        resp = _request_with_retry(
            requests.post,
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": config.MAX_TOKENS,
                "system": system,
                "messages": conv,
                "tools": self._convert_tools(tools),
                "stream": stream,
            },
            timeout=60,
            stream=stream,
        )
        resp.raise_for_status()

        if not stream:
            data = resp.json()
            content_text = ""
            tool_calls = []
            for block in data.get("content", []):
                if block["type"] == "text":
                    content_text += block["text"]
                elif block["type"] == "tool_use":
                    tool_calls.append({"id": block["id"], "name": block["name"], "arguments": block["input"]})
            u = data.get("usage", {}) or {}
            usage = {
                "input": u.get("input_tokens", 0),
                "output": u.get("output_tokens", 0),
                "total": u.get("input_tokens", 0) + u.get("output_tokens", 0),
            }
            return {"content": content_text, "tool_calls": tool_calls, "raw_message": data, "usage": usage}

        content_text = ""
        tool_calls = []
        current_block = None
        usage = {"input": 0, "output": 0, "total": 0}

        for line in resp.iter_lines():
            if not line:
                continue
            line = line.decode("utf-8")
            if not line.startswith("data: "):
                continue
            try:
                event = json.loads(line[len("data: "):])
            except Exception:
                continue

            etype = event.get("type")

            if etype == "content_block_start":
                block = event.get("content_block", {})
                if block.get("type") == "tool_use":
                    current_block = {"id": block.get("id"), "name": block.get("name"), "arguments": ""}
                else:
                    current_block = None

            elif etype == "content_block_delta":
                delta = event.get("delta", {})
                if delta.get("type") == "text_delta":
                    piece = delta.get("text", "")
                    content_text += piece
                    on_token(piece)
                elif delta.get("type") == "input_json_delta" and current_block is not None:
                    current_block["arguments"] += delta.get("partial_json", "")

            elif etype == "content_block_stop":
                if current_block is not None:
                    try:
                        args = json.loads(current_block["arguments"] or "{}")
                    except Exception:
                        args = {}
                    tool_calls.append({"id": current_block["id"], "name": current_block["name"], "arguments": args})
                    current_block = None

            elif etype == "message_start":
                u = event.get("message", {}).get("usage", {})
                usage["input"] = u.get("input_tokens", 0)

            elif etype == "message_delta":
                u = event.get("usage", {})
                if u:
                    usage["output"] = u.get("output_tokens", 0)

        usage["total"] = usage.get("input", 0) + usage.get("output", 0)
        return {"content": content_text, "tool_calls": tool_calls, "raw_message": None, "usage": usage}




class GeminiProvider(BaseProvider):
    """Google Gemini provider - Free tier via AI Studio"""
    name = "gemini"

    def __init__(self, api_key, model="gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    def chat(self, messages, tools=None, on_token=None):
        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}

        contents = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "system":
                contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})

        payload = {"contents": contents}

        try:
            resp = _request_with_retry(requests.post, url, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            candidates = data.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                response_text = parts[0].get("text", "") if parts else ""

                return {
                    "content": response_text,
                    "tool_calls": [],
                    "raw_message": None,
                    "usage": {"input": 0, "output": len(response_text.split()), "total": len(response_text.split())}
                }
            else:
                return {"content": "[error] No response from Gemini", "tool_calls": [], "raw_message": None, "usage": {}}

        except Exception as e:
            return {"content": f"[error] {e}", "tool_calls": [], "raw_message": None, "usage": {}}


def get_provider(name: str = None):
    name = (name or config.DEFAULT_PROVIDER).lower()
    if name == "groq":
        return OpenAICompatProvider(
            config.GROQ_API_KEY, "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"
        )
    if name == "claude":
        return ClaudeProvider(config.ANTHROPIC_API_KEY)
    if name == "openai":
        return OpenAICompatProvider(config.OPENAI_API_KEY, config.OPENAI_BASE_URL, "gpt-4o-mini")
    if name == "mimo":
        backup = [k for k in [config.MIMO_BACKUP_KEY] if k]
        return OpenAICompatProvider(config.MIMO_API_KEY, config.MIMO_BASE_URL, config.MIMO_MODEL, backup_keys=backup)
    if name == "custom":
        return OpenAICompatProvider(config.CUSTOM_API_KEY, config.CUSTOM_BASE_URL, config.CUSTOM_MODEL)
    if name == "mistral":
        return OpenAICompatProvider(config.MISTRAL_API_KEY, "https://api.mistral.ai/v1", "mistral-small-latest")
    if name == "cerebras":
        return OpenAICompatProvider(config.CEREBRAS_API_KEY, "https://api.cerebras.ai/v1", "gpt-oss-120b")
    if name == "cloudflare":
        return CloudflareProvider(config.CLOUDFLARE_API_TOKEN, config.CLOUDFLARE_ACCOUNT_ID)
    if name == "openrouter":
        return OpenAICompatProvider(config.OPENROUTER_API_KEY, "https://openrouter.ai/api/v1", "meta-llama/llama-3.3-70b-instruct:free")
    if name == "haimaker":
        return OpenAICompatProvider(config.HAIMAKER_API_KEY, config.HAIMAKER_BASE_URL, "gpt-4o-mini")
    if name == "gemini":
        return GeminiProvider(config.GEMINI_API_KEY)

    import custom_providers
    p = custom_providers.get_by_name(name)
    if p:
        return OpenAICompatProvider(p["api_key"], p["base_url"], p["model"])

    raise ValueError(f"Provider '{name}' tidak dikenal: {name}")


# ========================================
# AUTO ROUTER - 9 provider, auto-fallback
# ========================================

ROUTER_PRIORITY = [
    # (name, api_key_check, reason)
    ("groq",      "GROQ_API_KEY",      "Fastest (0.5s)"),
    ("cerebras",  "CEREBRAS_API_KEY",  "Fast (0.7s)"),
    ("mistral",   "MISTRAL_API_KEY",   "Fast (0.8s)"),
    ("gemini",    "GEMINI_API_KEY",    "Free 1M tokens/day"),
    ("mimo",      "MIMO_API_KEY",      "MiMo v2.5 + backup"),
    ("openrouter","OPENROUTER_API_KEY","Many free models"),
    ("haimaker",  "HAIMAKER_API_KEY",  "GPT-4o-mini"),
    ("openai",    "OPENAI_API_KEY",    "GPT-4o"),
    ("claude",    "ANTHROPIC_API_KEY", "Claude"),
]

BLACKOUT = {}  # provider -> until_timestamp (temporary ban on 429)


class AutoRouter(BaseProvider):
    """Auto-fallback router. Coba provider sesuai priority, skip yang limit/error."""
    name = "auto"

    def __init__(self):
        self.context_window = 128_000  # default
        # Build available providers (skip ones without API key)
        self.available = []
        for pname, key_attr, reason in ROUTER_PRIORITY:
            key = getattr(config, key_attr, "")
            if key:
                self.available.append((pname, reason))
        self.current_provider = None
        self.current_name = None
        self._last_msg = ""

    def _pick_provider(self):
        """Pick next available provider (skip blacked-out ones)."""
        import time as _time
        now = _time.time()
        for pname, reason in self.available:
            ban_until = BLACKOUT.get(pname, 0)
            if ban_until and now < ban_until:
                continue
            return pname, reason
        # All blacked out? Reset and try first one
        BLACKOUT.clear()
        if self.available:
            return self.available[0]
        return None, None

    def _ban(self, provider_name, seconds=60):
        """Temporarily ban a provider."""
        import time as _time
        BLACKOUT[provider_name] = _time.time() + seconds

    def chat(self, messages, tools=None, on_token=None):
        import time as _time

        errors_log = []
        last_result = None

        for attempt in range(len(self.available)):
            pname, reason = self._pick_provider()
            if pname is None:
                break

            provider = get_provider(pname)

            try:
                start = _time.time()
                result = provider.chat(messages, tools, on_token=on_token)
                elapsed = _time.time() - start

                content = result.get("content", "")
                tool_calls = result.get("tool_calls", [])

                # Check for error responses
                if content.startswith("[error]"):
                    err_msg = content
                    # Ban on rate limit
                    if "429" in err_msg or "rate" in err_msg.lower() or "limit" in err_msg.lower():
                        self._ban(pname, 120)
                        errors_log.append(f"❌ {pname}: {err_msg[:80]}")
                        continue
                    # Ban on auth errors
                    if "401" in err_msg or "402" in err_msg or "Unauthorized" in err_msg:
                        self._ban(pname, 3600)
                        errors_log.append(f"❌ {pname}: {err_msg[:80]}")
                        continue
                    # Other errors, skip but don't ban long
                    self._ban(pname, 30)
                    errors_log.append(f"❌ {pname}: {err_msg[:80]}")
                    continue

                # SUCCESS
                self.current_provider = provider
                self.current_name = pname
                self._last_msg = f"✅ [{pname}] ({elapsed:.1f}s)"

                return result

            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate" in err_str.lower():
                    self._ban(pname, 120)
                else:
                    self._ban(pname, 30)
                errors_log.append(f"❌ {pname}: {err_str[:80]}")
                continue

        # All failed
        all_errors = "\n".join(errors_log)
        return {
            "content": f"[error] Semua provider gagal:\n{all_errors}",
            "tool_calls": [],
            "raw_message": None,
            "usage": {},
        }
