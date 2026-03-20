"""
MiroFish engine connection configuration.

Reads from environment variables with sensible defaults for local Docker
development. All timeouts are in seconds.

Unit convention: timeouts in seconds, ports as integers.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _env_float(var_name: str, default: str) -> float:
    """Read an env var as float with a clear error message."""
    raw = os.environ.get(var_name, default)
    try:
        return float(raw)
    except (ValueError, TypeError):
        raise ValueError(
            f"Environment variable {var_name}={raw!r} is not a valid number"
        ) from None


def _env_int(var_name: str, default: str) -> int:
    """Read an env var as int with a clear error message."""
    raw = os.environ.get(var_name, default)
    try:
        return int(raw)
    except (ValueError, TypeError):
        raise ValueError(
            f"Environment variable {var_name}={raw!r} is not a valid integer"
        ) from None


@dataclass
class MiroFishConfig:
    """Connection parameters for the MiroFish simulation engine.

    The engine runs as a separate Docker container (AGPL-3.0 isolation).
    Communication is REST-only via the Flask backend on port 5001.
    """
    base_url: str = "http://localhost:5001"
    timeout: float = 60.0           # default per-request timeout
    long_timeout: float = 300.0     # for /prepare, /start, /interview
    max_retries: int = 3
    retry_backoff_base: float = 2.0  # exponential: 2s, 4s, 8s
    connect_timeout: float = 10.0

    @classmethod
    def from_env(cls) -> MiroFishConfig:
        """Build config from MIROFISH_* environment variables."""
        return cls(
            base_url=os.environ.get(
                "MIROFISH_BASE_URL", "http://localhost:5001"
            ).rstrip("/"),
            timeout=_env_float("MIROFISH_TIMEOUT", "60"),
            long_timeout=_env_float("MIROFISH_LONG_TIMEOUT", "300"),
            max_retries=_env_int("MIROFISH_MAX_RETRIES", "3"),
            retry_backoff_base=_env_float("MIROFISH_RETRY_BACKOFF", "2.0"),
            connect_timeout=_env_float("MIROFISH_CONNECT_TIMEOUT", "10"),
        )
