"""
Pencatat pemakaian token & estimasi biaya harian, per provider.
Data disimpan di usage_log.json, format: {"2026-07-07": {"mimo": {...}}}
"""
import json
import os
from datetime import date
import config

# Harga perkiraan per 1 juta token (USD): (input, output). Model yang gak ada
# di sini dianggap gratis/gak diketahui (cost=0), tetap dicatat token-nya.
PRICING = {
    "claude-sonnet-4-6": (3.0, 15.0),
    "gpt-4o-mini": (0.15, 0.6),
    "llama-3.3-70b-versatile": (0.59, 0.79),
}


def _price_for(model):
    return PRICING.get(model, (0.0, 0.0))


def _load():
    if not os.path.exists(config.USAGE_LOG_FILE):
        return {}
    try:
        with open(config.USAGE_LOG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data):
    try:
        with open(config.USAGE_LOG_FILE, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def log_usage(provider_name, model, input_tokens, output_tokens):
    today = date.today().isoformat()
    data = _load()
    day = data.setdefault(today, {})
    entry = day.setdefault(provider_name, {"model": model, "input": 0, "output": 0, "cost": 0.0})
    entry["model"] = model
    entry["input"] += input_tokens or 0
    entry["output"] += output_tokens or 0
    in_price, out_price = _price_for(model)
    cost = ((input_tokens or 0) / 1_000_000) * in_price + ((output_tokens or 0) / 1_000_000) * out_price
    entry["cost"] = entry.get("cost", 0.0) + cost
    _save(data)


def get_today_stats():
    today = date.today().isoformat()
    return _load().get(today, {})


def get_all_stats():
    return _load()
