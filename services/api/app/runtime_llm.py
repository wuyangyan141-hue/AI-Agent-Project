"""User-selectable offline/online LLM runtime, persisted in SQLite preferences."""
from __future__ import annotations

import json
from dataclasses import asdict, replace
from typing import Any, Literal

from .database import store
from .knowledge.config import Settings

PREF_KEY = 'llm_runtime'
Mode = Literal['offline', 'online']

# Common OpenAI-compatible endpoints for the settings UI.
PROVIDER_PRESETS = [
    {
        'id': 'dashscope',
        'label': '阿里云百炼 / DashScope',
        'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'model': 'qwen-plus',
    },
    {
        'id': 'openai',
        'label': 'OpenAI',
        'base_url': 'https://api.openai.com/v1',
        'model': 'gpt-4o-mini',
    },
    {
        'id': 'custom',
        'label': '自定义 OpenAI 兼容接口',
        'base_url': '',
        'model': '',
    },
]


def _env_defaults() -> dict[str, str]:
    base = Settings.from_env()
    online = bool(base.llm_api_key and base.llm_model)
    return {
        'mode': 'online' if online else 'offline',
        'provider': 'dashscope' if 'dashscope' in (base.llm_base_url or '') else ('openai' if online else 'custom'),
        'llm_model': base.llm_model or '',
        'llm_api_key': base.llm_api_key or '',
        'llm_base_url': base.llm_base_url or 'https://api.openai.com/v1',
    }


def _read_override() -> dict[str, Any]:
    with store.connect() as db:
        raw = store.get_preference(db, PREF_KEY, '')
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _mask_key(key: str) -> str:
    token = (key or '').strip()
    if not token:
        return ''
    if len(token) <= 8:
        return '*' * len(token)
    return token[:3] + '*' * max(4, len(token) - 7) + token[-4:]


def merged_llm_fields() -> dict[str, Any]:
    """Env defaults overwritten by user-saved runtime preference."""
    data = {**_env_defaults(), **_read_override()}
    mode = data.get('mode') if data.get('mode') in {'offline', 'online'} else 'offline'
    model = str(data.get('llm_model') or '').removeprefix('openai:').strip()
    key = str(data.get('llm_api_key') or '').strip()
    base_url = str(data.get('llm_base_url') or '').strip() or 'https://api.openai.com/v1'
    provider = str(data.get('provider') or 'custom').strip() or 'custom'
    if mode == 'offline':
        # Force offline even if env still has a key.
        return {
            'mode': 'offline',
            'provider': provider,
            'llm_model': model,
            'llm_api_key': '',
            'llm_base_url': base_url,
            'has_api_key': bool(key),
            'api_key_masked': _mask_key(key),
            'online_ready': False,
            'agent_mode': 'demo',
        }
    online_ready = bool(model and key and base_url)
    return {
        'mode': 'online',
        'provider': provider,
        'llm_model': model,
        'llm_api_key': key if online_ready else '',
        'llm_base_url': base_url,
        'has_api_key': bool(key),
        'api_key_masked': _mask_key(key),
        'online_ready': online_ready,
        'agent_mode': 'langchain' if online_ready else 'demo',
    }


def active_settings() -> Settings:
    """Settings used by agent / knowledge / review grading."""
    base = Settings.from_env()
    fields = merged_llm_fields()
    return replace(
        base,
        llm_model=fields['llm_model'] if fields['mode'] == 'online' else '',
        llm_api_key=fields['llm_api_key'] if fields['mode'] == 'online' else '',
        llm_base_url=fields['llm_base_url'],
        # Chat and review reuse the chat credential unless embedding was set separately in env.
        embedding_api_key=fields['llm_api_key'] if fields['mode'] == 'online' and fields['llm_api_key'] else base.embedding_api_key,
        embedding_base_url=fields['llm_base_url'] if fields['mode'] == 'online' else base.embedding_base_url,
    )


def public_config() -> dict[str, Any]:
    fields = merged_llm_fields()
    return {
        'mode': fields['mode'],
        'provider': fields['provider'],
        'llm_model': fields['llm_model'],
        'llm_base_url': fields['llm_base_url'],
        'has_api_key': fields['has_api_key'],
        'api_key_masked': fields['api_key_masked'],
        'online_ready': fields['online_ready'],
        'agent_mode': fields['agent_mode'],
        'presets': PROVIDER_PRESETS,
        'hint': (
            '在线模式需要填写模型名、Base URL 和 API Key（OpenAI 兼容）。'
            '离线模式只用本地检索与模板，不会调用外网模型。'
        ),
    }


def save_config(payload: dict[str, Any]) -> dict[str, Any]:
    current = _read_override()
    env = _env_defaults()
    mode = str(payload.get('mode') or current.get('mode') or env['mode']).strip()
    if mode not in {'offline', 'online'}:
        raise ValueError('mode 只能是 offline 或 online。')
    provider = str(payload.get('provider') or current.get('provider') or 'custom').strip()[:40]
    model = str(payload.get('llm_model') if 'llm_model' in payload else current.get('llm_model') or env['llm_model']).removeprefix('openai:').strip()[:120]
    base_url = str(payload.get('llm_base_url') if 'llm_base_url' in payload else current.get('llm_base_url') or env['llm_base_url']).strip()[:300]
    # Keep previous key when the client sends blank / masked placeholder.
    incoming_key = payload.get('llm_api_key') if 'llm_api_key' in payload else None
    if incoming_key is None:
        key = str(current.get('llm_api_key') or env['llm_api_key']).strip()
    else:
        token = str(incoming_key).strip()
        if not token or '*' in token:
            key = str(current.get('llm_api_key') or env['llm_api_key']).strip()
        else:
            key = token[:200]
    if mode == 'online' and not (model and key and base_url):
        raise ValueError('在线模式请填写模型名、API Key 和 Base URL。')
    if base_url and not (base_url.startswith('http://') or base_url.startswith('https://')):
        raise ValueError('Base URL 需要以 http:// 或 https:// 开头。')
    saved = {
        'mode': mode,
        'provider': provider or 'custom',
        'llm_model': model,
        'llm_api_key': key,
        'llm_base_url': base_url or 'https://api.openai.com/v1',
    }
    with store.connect() as db:
        store.set_preference(db, PREF_KEY, json.dumps(saved, ensure_ascii=False))
    return public_config()


def apply_runtime(agent) -> dict[str, Any]:
    """Hot-reload agent + knowledge singleton after settings change."""
    from .knowledge.integration import _service, get_knowledge

    settings = active_settings()
    agent.apply_settings(settings)
    _service.cache_clear()
    # Touch the new service so status reflects the active config immediately.
    get_knowledge()
    return public_config()
