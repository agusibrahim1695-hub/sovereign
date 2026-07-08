"""
Penyimpanan multi custom endpoint (JSON), terpisah dari .env supaya bisa
banyak (4-5+) sekaligus, masing-masing punya nama & role (chat/coding/dll).
"""
import json
import os
import config


def _load():
    if not os.path.exists(config.CUSTOM_PROVIDERS_FILE):
        return []
    try:
        with open(config.CUSTOM_PROVIDERS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def _save(providers):
    with open(config.CUSTOM_PROVIDERS_FILE, "w") as f:
        json.dump(providers, f, ensure_ascii=False, indent=2)


def list_providers():
    return _load()


def get_by_name(name):
    for p in _load():
        if p["name"] == name:
            return p
    return None


def get_by_role(role):
    for p in _load():
        if p.get("role") == role:
            return p
    return None


def add_provider(name, base_url, api_key, model, role=None):
    providers = [p for p in _load() if p["name"] != name]
    if role:
        for p in providers:
            if p.get("role") == role:
                p["role"] = None
    providers.append({"name": name, "base_url": base_url, "api_key": api_key, "model": model, "role": role})
    _save(providers)


def delete_provider(name):
    providers = [p for p in _load() if p["name"] != name]
    _save(providers)
