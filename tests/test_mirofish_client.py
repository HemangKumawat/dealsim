"""Tests for MiroFishClient — all HTTP calls are mocked."""
import pytest

from dealsim_mvp.core.mirofish_client import MiroFishClient, MiroFishAPIError
from dealsim_mvp.core.mirofish_config import MiroFishConfig


class TestMiroFishConfig:
    def test_defaults(self):
        cfg = MiroFishConfig()
        assert cfg.base_url == "http://localhost:5001"
        assert cfg.timeout == 60.0
        assert cfg.max_retries == 3

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("MIROFISH_BASE_URL", "http://myhost:9999/")
        monkeypatch.setenv("MIROFISH_TIMEOUT", "120")
        monkeypatch.setenv("MIROFISH_MAX_RETRIES", "5")

        cfg = MiroFishConfig.from_env()
        assert cfg.base_url == "http://myhost:9999"  # trailing slash stripped
        assert cfg.timeout == 120.0
        assert cfg.max_retries == 5

    def test_from_env_invalid_timeout(self, monkeypatch):
        monkeypatch.setenv("MIROFISH_TIMEOUT", "not_a_number")
        with pytest.raises(ValueError, match="MIROFISH_TIMEOUT"):
            MiroFishConfig.from_env()

    def test_from_env_defaults(self, monkeypatch):
        """Without env vars, from_env uses defaults."""
        monkeypatch.delenv("MIROFISH_BASE_URL", raising=False)
        monkeypatch.delenv("MIROFISH_TIMEOUT", raising=False)
        cfg = MiroFishConfig.from_env()
        assert cfg.base_url == "http://localhost:5001"


class TestMiroFishAPIError:
    def test_error_message(self):
        err = MiroFishAPIError(500, "Something broke", "/api/test")
        assert "500" in str(err)
        assert "/api/test" in str(err)
        assert err.status_code == 500
        assert err.path == "/api/test"


class TestClientInit:
    def test_creates_without_connection(self):
        cfg = MiroFishConfig(base_url="http://test:5001")
        client = MiroFishClient(cfg)
        assert client.config.base_url == "http://test:5001"
        assert client._client is None
