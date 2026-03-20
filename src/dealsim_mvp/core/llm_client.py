"""
Lightweight OpenAI-compatible LLM client for DealSim.

Calls any OpenAI-compatible chat completion API (DeepSeek, OpenAI, etc.)
to generate negotiation opponent responses. No external SDK dependency —
just httpx calling the standard /v1/chat/completions endpoint.

Cost estimate: ~$0.003/simulation with DeepSeek, ~$0.035 with GPT-4o-mini.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """Configuration for an OpenAI-compatible chat completion endpoint."""
    api_key: str
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"
    temperature: float = 0.7
    max_tokens: int = 300
    timeout: float = 30.0


class LLMClient:
    """Async client for OpenAI-compatible chat completion API."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.config.timeout,
            )
        return self._client

    async def chat_completion(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> str:
        """
        Send a chat completion request and return the assistant's response text.

        Args:
            system_prompt: The persona system prompt (defines opponent personality
                           and constraints).
            messages: Conversation history as a list of
                      {"role": "user"/"assistant", "content": "..."} dicts.

        Returns:
            The LLM's response text (content of the first choice).

        Raises:
            httpx.HTTPStatusError: on 4xx/5xx API responses.
            httpx.RequestError: on connection or timeout failures.
        """
        client = await self._get_client()

        full_messages = [{"role": "system", "content": system_prompt}] + messages

        payload = {
            "model": self.config.model,
            "messages": full_messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        resp = await client.post("/chat/completions", json=payload)
        resp.raise_for_status()

        data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def health_check(self) -> bool:
        """
        Verify the API key is valid and the endpoint is reachable.

        Sends a minimal 5-token request. Returns True on HTTP 200, False on
        any error (connection refused, auth failure, timeout, etc.).
        """
        try:
            client = await self._get_client()
            resp = await client.post(
                "/chat/completions",
                json={
                    "model": self.config.model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 5,
                },
            )
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        """Release the underlying httpx connection pool."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
