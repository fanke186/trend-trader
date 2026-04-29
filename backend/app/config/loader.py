from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - exercised only in minimal envs
    yaml = None


DEFAULT_CONFIG: dict[str, Any] = {
    "active": {
        "quote_channel": "mootdx",
        "trade_mode": "dry_run",
        "notify_channel": "hermes",
        "ai_profile": "deepseek",
    },
    "ai": {
        "profiles": [
            {
                "name": "deepseek",
                "provider": "deepseek",
                "base_url": "https://api.deepseek.com",
                "api_key_env": "DEEPSEEK_API_KEY",
                "model": "deepseek-v4-pro",
                "temperature": 0.2,
                "max_tokens": 4096,
                "timeout_seconds": 60,
                "active": True,
            }
        ]
    },
    "quote": {
        "mootdx": {"enabled": True, "market": "std", "multithread": True, "heartbeat": True, "timeout_seconds": 5, "retry": 3},
        "jvquant": {"enabled": False, "token_env": "JVQUANT_TOKEN", "default_level": "lv1", "timeout_seconds": 10, "reconnect_seconds": 3},
    },
    "trading": {
        "mode": "dry_run",
        "miniqmt": {"gateway_url": "http://127.0.0.1:8800", "timeout_seconds": 10, "retry": 3},
        "paper": {"initial_cash": 100000, "commission_rate": 0.00025, "stamp_duty": 0.001, "min_commission": 5},
    },
    "notify": {
        "hermes": {"enabled": True, "binary": "/Users/yaya/.local/bin/hermes", "send_env": "TREND_TRADER_HERMES_SEND"},
        "wechat": {"enabled": False, "webhook_url_env": "WECHAT_WEBHOOK_URL"},
        "dingtalk": {"enabled": False, "webhook_url_env": "DINGTALK_WEBHOOK_URL", "secret_env": "DINGTALK_SECRET"},
    },
    "kline_db": {"db_path": "kline.duckdb", "parquet_dir": "kline_parquet", "years_back": 15, "frequencies": ["1d", "1w", "1M"], "auto_update_after": "15:30"},
}


class ConfigLoader:
    """YAML configuration loader with TREND_TRADER_* environment overrides."""

    def __init__(self, config_path: Path) -> None:
        self._path = config_path
        self._data = copy.deepcopy(DEFAULT_CONFIG)
        self.reload()

    @property
    def path(self) -> Path:
        return self._path

    def reload(self) -> None:
        data = copy.deepcopy(DEFAULT_CONFIG)
        if self._path.exists():
            if yaml is None:
                raise RuntimeError("PyYAML is required to load config.yaml")
            with open(self._path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
            if not isinstance(loaded, dict):
                raise ValueError(f"config file must contain a mapping: {self._path}")
            _deep_merge(data, loaded)
        self._data = data
        self._apply_env_overrides()

    def _apply_env_overrides(self) -> None:
        prefix = "TREND_TRADER_"
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
            rest = key[len(prefix):].lower()
            if "__" in rest:
                parts = rest.split("__")
                self._set_path(parts, value)
                continue
            section, _, subkey = rest.partition("_")
            if section and subkey and isinstance(self._data.get(section), dict):
                self._data[section][subkey] = _coerce_env_value(value)

    def _set_path(self, parts: list[str], value: str) -> None:
        node: dict[str, Any] = self._data
        for part in parts[:-1]:
            child = node.get(part)
            if not isinstance(child, dict):
                child = {}
                node[part] = child
            node = child
        if parts:
            node[parts[-1]] = _coerce_env_value(value)

    def get_active_ai_profile(self) -> dict[str, Any]:
        active_name = self._data.get("active", {}).get("ai_profile", "deepseek")
        for profile in self._data.get("ai", {}).get("profiles", []):
            if profile.get("name") == active_name and profile.get("active", True):
                return dict(profile)
        available = [p.get("name") for p in self._data.get("ai", {}).get("profiles", [])]
        raise ValueError(f"Active AI profile '{active_name}' not found or inactive. Available: {available}")

    def get_active_quote_channel(self) -> tuple[str, dict[str, Any]]:
        channel = self._data.get("active", {}).get("quote_channel", "mootdx")
        config = self._data.get("quote", {}).get(channel, {})
        if not config or not config.get("enabled", True):
            raise ValueError(f"Quote channel '{channel}' is disabled or not configured")
        return str(channel), dict(config)

    def masked(self) -> dict[str, Any]:
        return _mask(copy.deepcopy(self._data))

    @property
    def raw(self) -> dict[str, Any]:
        return copy.deepcopy(self._data)

    @property
    def trading(self) -> dict[str, Any]:
        return dict(self._data.get("trading", {}))

    @property
    def notify(self) -> dict[str, Any]:
        return dict(self._data.get("notify", {}))

    @property
    def kline_db(self) -> dict[str, Any]:
        return dict(self._data.get("kline_db", {}))


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _coerce_env_value(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _mask(value: Any) -> Any:
    if isinstance(value, dict):
        masked: dict[str, Any] = {}
        for key, item in value.items():
            lowered = key.lower()
            if "key" in lowered or "token" in lowered or "secret" in lowered or "password" in lowered:
                masked[key] = "***"
            else:
                masked[key] = _mask(item)
        return masked
    if isinstance(value, list):
        return [_mask(item) for item in value]
    return value
