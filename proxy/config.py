"""JSON configuration loading and validation (standard library only)."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when the configuration file is missing or invalid."""


@dataclass(frozen=True)
class Backend:
    host: str
    port: int


@dataclass(frozen=True)
class ListenAddress:
    host: str
    port: int


@dataclass(frozen=True)
class RouterConfig:
    listen: ListenAddress
    routes: dict[str, Backend]


def _port(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
        raise ConfigError(f"{field} must be an integer between 1 and 65535")
    return value


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{field} must be a mapping")
    return value


def _normalise_hostname(hostname: str) -> str:
    return hostname.lower().rstrip(".")


def load_config(path: str | Path) -> RouterConfig:
    try:
        with Path(path).open("r", encoding="utf-8") as config_file:
            raw = json.load(config_file)
    except OSError as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON in {path}: {exc}") from exc

    root = _mapping(raw, "configuration")
    listen = _mapping(root.get("listen"), "listen")
    listen_host = listen.get("host")
    if not isinstance(listen_host, str) or not listen_host:
        raise ConfigError("listen.host must be a non-empty string")

    raw_routes = _mapping(root.get("routes"), "routes")
    routes: dict[str, Backend] = {}
    for hostname, destination in raw_routes.items():
        if not isinstance(hostname, str) or not hostname:
            raise ConfigError("route hostnames must be non-empty strings")
        backend = _mapping(destination, f"routes.{hostname}")
        backend_host = backend.get("host")
        if not isinstance(backend_host, str) or not backend_host:
            raise ConfigError(f"routes.{hostname}.host must be a non-empty string")
        key = _normalise_hostname(hostname)
        if key in routes:
            raise ConfigError(f"duplicate route hostname: {hostname}")
        routes[key] = Backend(backend_host, _port(backend.get("port"), f"routes.{hostname}.port"))

    return RouterConfig(
        listen=ListenAddress(listen_host, _port(listen.get("port", 25565), "listen.port")),
        routes=routes,
    )
