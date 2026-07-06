"""
Unified interface ke berbagai LLM API. Semua return format sama:
{
  "content": "<text dari model, bisa kosong>",
  "tool_calls": [{"id": "...", "name": "...", "arguments": {...}}]
}
Tinggal nambah class baru kalau mau provider lain (deepseek, openrouter, dll —
selama API-nya OpenAI-compatible, tinggal reuse OpenAICompatProvider).
"""
import json
import requests
import config


class BaseProvider:
    name = "base"

    def chat(self, messages, tools):
        raise NotImplementedError


CONTEXT_WINDOWS = {
    "llama-3.3-70b-versatile": 128_000,
    "claude-sonnet-4-6": 200_000,
    "gpt-4o-mini": 128_000,
    "mimo-v2.5": 128_000,
    "mimo": 128_000,
}


class OpenAICompatProvider(BaseProvider):
    """Dipakai untuk Groq, OpenAI asli, atau LLM lokal/openrouter yang OpenAI-compatible."""

    def __init__(self, api_key, base_url, model):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.context_window = CONTEXT_WINDOWS.get(model, 128_000)

    def chat(self, messages, tools):
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
                "max_tokens": 4096,
            },
            timeout=60,
        )
        resp.raise_for_status()
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
        """Pisahkan system prompt, convert tool-result messages ke format Anthropic."""
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

    def chat(self, messages, tools):
        system, conv = self._convert_messages(messages)
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": 4096,
                "system": system,
                "messages": conv,
                "tools": self._convert_tools(tools),
            },
            timeout=60,
        )
        resp.raise_for_status()
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
        return OpenAICompatProvider(config.MIMO_API_KEY, config.MIMO_BASE_URL, config.MIMO_MODEL)
    raise ValueError(f"Provider '{name}' tidak dikenal. Pilihan: groq, claude, openai, mimo")
