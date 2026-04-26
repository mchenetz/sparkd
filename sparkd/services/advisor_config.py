"""Active advisor provider/model configuration.

State lives in two places:
- ~/.sparkd/advisor.json — non-secret state (active provider, per-provider
  model + base_url overrides).
- OS keyring — API keys, one per provider id (e.g. `anthropic_api_key`,
  `openai_api_key`).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from sparkd import paths
from sparkd import secrets as sparkd_secrets
from sparkd.advisor import AdvisorPort, AnthropicAdapter, OpenAICompatAdapter
from sparkd.advisor.providers import PROVIDERS, get_provider


def _config_path() -> Path:
    return paths.root() / "advisor.json"


@dataclass
class ProviderState:
    model: str = ""
    base_url: str | None = None


@dataclass
class AdvisorConfig:
    active_provider: str = "anthropic"
    providers: dict[str, ProviderState] = field(default_factory=dict)

    def get_state(self, provider_id: str) -> ProviderState:
        return self.providers.setdefault(provider_id, ProviderState())


def _key_name(provider_id: str) -> str:
    return f"{provider_id}_api_key"


def load_config() -> AdvisorConfig:
    path = _config_path()
    if not path.exists():
        return AdvisorConfig()
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return AdvisorConfig()
    cfg = AdvisorConfig(
        active_provider=raw.get("active_provider", "anthropic"),
        providers={
            pid: ProviderState(**(p or {}))
            for pid, p in (raw.get("providers") or {}).items()
        },
    )
    return cfg


def save_config(cfg: AdvisorConfig) -> None:
    paths.ensure()
    path = _config_path()
    path.write_text(
        json.dumps(
            {
                "active_provider": cfg.active_provider,
                "providers": {
                    pid: {"model": s.model, "base_url": s.base_url}
                    for pid, s in cfg.providers.items()
                },
            },
            indent=2,
        )
    )


def get_api_key(provider_id: str) -> str:
    if provider_id == "anthropic":
        # Honor the legacy key location so existing setups keep working.
        legacy = sparkd_secrets.get_secret("anthropic_api_key")
        if legacy:
            return legacy
    return sparkd_secrets.get_secret(_key_name(provider_id)) or ""


def set_api_key(provider_id: str, key: str) -> None:
    sparkd_secrets.set_secret(_key_name(provider_id), key)
    if provider_id == "anthropic":
        # Keep legacy key in sync.
        sparkd_secrets.set_secret("anthropic_api_key", key)


def has_api_key(provider_id: str) -> bool:
    p = get_provider(provider_id)
    if p is not None and not p.requires_key:
        return True  # local providers don't need a key
    return bool(get_api_key(provider_id))


def build_port(cfg: AdvisorConfig | None = None) -> AdvisorPort | None:
    """Instantiate the adapter for the currently-active provider, or None
    if there's no usable configuration yet (e.g. no key saved).
    """
    cfg = cfg or load_config()
    pdef = get_provider(cfg.active_provider)
    if pdef is None:
        return None
    state = cfg.get_state(cfg.active_provider)
    model = state.model or (pdef.models[0] if pdef.models else "")
    if not model:
        return None
    api_key = get_api_key(cfg.active_provider)
    if pdef.requires_key and not api_key:
        return None
    if pdef.family == "anthropic":
        return AnthropicAdapter(api_key=api_key, model=model)
    if pdef.family == "openai_compat":
        base_url = state.base_url or pdef.default_base_url
        return OpenAICompatAdapter(api_key=api_key, model=model, base_url=base_url)
    return None


def provider_summary() -> list[dict]:
    """Catalog for the UI: definitions + whether each provider is configured."""
    out = []
    for p in PROVIDERS:
        out.append(
            {
                "id": p.id,
                "label": p.label,
                "family": p.family,
                "requires_key": p.requires_key,
                "default_base_url": p.default_base_url,
                "base_url_editable": p.base_url_editable,
                "models": list(p.models),
                "notes": p.notes,
                "has_key": has_api_key(p.id),
            }
        )
    return out
