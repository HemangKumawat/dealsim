"""Tests for LLMClient — all HTTP calls are mocked."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dealsim_mvp.core.llm_client import LLMClient, LLMConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def config():
    return LLMConfig(
        api_key="test-key",
        base_url="https://api.test.com/v1",
        model="test-model",
    )


@pytest.fixture
def client(config):
    return LLMClient(config)


def _mock_response(content: str, status: int = 200) -> MagicMock:
    """Build a mock httpx response with the given chat completion payload."""
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# LLMConfig
# ---------------------------------------------------------------------------

class TestLLMConfig:
    def test_defaults(self):
        cfg = LLMConfig(api_key="sk-abc")
        assert cfg.base_url == "https://api.deepseek.com/v1"
        assert cfg.model == "deepseek-chat"
        assert cfg.temperature == 0.7
        assert cfg.max_tokens == 300
        assert cfg.timeout == 30.0

    def test_custom_values(self):
        cfg = LLMConfig(
            api_key="sk-openai",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=200,
        )
        assert cfg.model == "gpt-4o-mini"
        assert cfg.temperature == 0.3


# ---------------------------------------------------------------------------
# chat_completion
# ---------------------------------------------------------------------------

class TestChatCompletion:
    def test_success_returns_content(self, client):
        mock_resp = _mock_response("I can offer $95,000.")

        async def run():
            with patch.object(client, "_get_client") as mock_get:
                mock_http = AsyncMock()
                mock_http.post = AsyncMock(return_value=mock_resp)
                mock_get.return_value = mock_http
                return await client.chat_completion(
                    "You are a recruiter.",
                    [{"role": "user", "content": "I want $100,000"}],
                )

        result = asyncio.run(run())
        assert result == "I can offer $95,000."

    def test_system_prompt_is_prepended(self, client):
        """Verify system message is first in the payload sent to the API."""
        mock_resp = _mock_response("counter offer text")
        captured_payload = {}

        async def capturing_post(path, json=None, **kwargs):
            captured_payload.update(json or {})
            return mock_resp

        async def run():
            with patch.object(client, "_get_client") as mock_get:
                mock_http = AsyncMock()
                mock_http.post = AsyncMock(side_effect=capturing_post)
                mock_get.return_value = mock_http
                await client.chat_completion(
                    "system content",
                    [{"role": "user", "content": "user content"}],
                )

        asyncio.run(run())
        messages = captured_payload["messages"]
        assert messages[0] == {"role": "system", "content": "system content"}
        assert messages[1] == {"role": "user", "content": "user content"}

    def test_config_params_sent_in_payload(self, client):
        """model, temperature, and max_tokens from LLMConfig appear in payload."""
        mock_resp = _mock_response("ok")
        captured_payload = {}

        async def capturing_post(path, json=None, **kwargs):
            captured_payload.update(json or {})
            return mock_resp

        async def run():
            with patch.object(client, "_get_client") as mock_get:
                mock_http = AsyncMock()
                mock_http.post = AsyncMock(side_effect=capturing_post)
                mock_get.return_value = mock_http
                await client.chat_completion("sys", [])

        asyncio.run(run())
        assert captured_payload["model"] == "test-model"
        assert captured_payload["temperature"] == 0.7
        assert captured_payload["max_tokens"] == 300

    def test_raises_on_http_error(self, client):
        """raise_for_status propagates through chat_completion."""
        import httpx

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=MagicMock()
        )

        async def run():
            with patch.object(client, "_get_client") as mock_get:
                mock_http = AsyncMock()
                mock_http.post = AsyncMock(return_value=mock_resp)
                mock_get.return_value = mock_http
                await client.chat_completion("sys", [])

        with pytest.raises(Exception):
            asyncio.run(run())


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    def test_returns_true_on_200(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        async def run():
            with patch.object(client, "_get_client") as mock_get:
                mock_http = AsyncMock()
                mock_http.post = AsyncMock(return_value=mock_resp)
                mock_get.return_value = mock_http
                return await client.health_check()

        assert asyncio.run(run()) is True

    def test_returns_false_on_connection_error(self, client):
        async def run():
            with patch.object(client, "_get_client") as mock_get:
                mock_http = AsyncMock()
                mock_http.post = AsyncMock(side_effect=Exception("Connection refused"))
                mock_get.return_value = mock_http
                return await client.health_check()

        assert asyncio.run(run()) is False

    def test_returns_false_on_non_200_status(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 401

        async def run():
            with patch.object(client, "_get_client") as mock_get:
                mock_http = AsyncMock()
                mock_http.post = AsyncMock(return_value=mock_resp)
                mock_get.return_value = mock_http
                return await client.health_check()

        assert asyncio.run(run()) is False


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------

class TestClose:
    def test_close_calls_aclose(self, client):
        async def run():
            # Force client creation
            with patch.object(client, "_get_client") as mock_get:
                mock_http = AsyncMock()
                mock_http.is_closed = False
                mock_http.post = AsyncMock(return_value=_mock_response("hi"))
                mock_get.return_value = mock_http
                client._client = mock_http
                await client.close()
                mock_http.aclose.assert_called_once()

        asyncio.run(run())

    def test_close_is_safe_when_no_client(self, client):
        """close() should not raise if _get_client was never called."""
        assert client._client is None
        asyncio.run(client.close())  # should not raise
