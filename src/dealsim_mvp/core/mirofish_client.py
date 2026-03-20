"""
Lightweight async HTTP client for the MiroFish simulation engine.

Handles only the endpoints needed for DealSim negotiation:
  - Health check
  - Create simulation (single-agent negotiation opponent)
  - Prepare simulation (agent setup)
  - Interview agent (send user message, get opponent response)
  - Stop/close simulation

Follows the same patterns as orchestration/client.py (retry with exponential
backoff, structured error mapping, timeout tiers) but is self-contained
inside the dealsim package — no cross-repo imports.

AGPL-3.0 boundary: this client talks to MiroFish over REST only.
No MiroFish code is imported, copied, or linked.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from dealsim_mvp.core.mirofish_config import MiroFishConfig

logger = logging.getLogger(__name__)


class MiroFishAPIError(Exception):
    """Non-retryable error from MiroFish backend."""

    def __init__(self, status_code: int, detail: str, path: str = "") -> None:
        self.status_code = status_code
        self.detail = detail
        self.path = path
        super().__init__(f"MiroFish {status_code} on {path}: {detail[:200]}")


class MiroFishClient:
    """Async client for MiroFish REST API (Flask backend on port 5001).

    Usage::

        client = MiroFishClient(MiroFishConfig.from_env())
        try:
            result = await client.interview(sim_id, agent_id=0, prompt="...")
        finally:
            await client.close()
    """

    def __init__(self, config: MiroFishConfig) -> None:
        self.config = config
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=httpx.Timeout(
                    self.config.timeout,
                    connect=self.config.connect_timeout,
                ),
            )
        return self._client

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Send request with retries and structured error mapping.

        Retries on: 429 (rate limit), 502/503/504 (transient infra),
        httpx network errors. Does NOT retry 4xx client errors.
        """
        client = await self._get_client()
        last_exc: Exception | None = None

        for attempt in range(self.config.max_retries):
            try:
                kwargs: dict[str, Any] = {}
                if json is not None:
                    kwargs["json"] = json
                if params is not None:
                    kwargs["params"] = params
                if timeout is not None:
                    kwargs["timeout"] = timeout

                resp = await client.request(method, path, **kwargs)

                if resp.status_code < 400:
                    body = resp.json()
                    if isinstance(body, dict) and body.get("success") is False:
                        raise MiroFishAPIError(
                            resp.status_code,
                            body.get("error", "Unknown error"),
                            path,
                        )
                    return body

                # Rate limit — retryable
                if resp.status_code == 429:
                    retry_after = float(
                        resp.headers.get("Retry-After", 0)
                    )
                    wait = max(
                        retry_after,
                        self.config.retry_backoff_base ** attempt,
                    )
                    logger.warning(
                        "MiroFish 429 on %s — retry in %.1fs (attempt %d/%d)",
                        path, wait, attempt + 1, self.config.max_retries,
                    )
                    await asyncio.sleep(wait)
                    continue

                # Transient server errors — retryable
                if resp.status_code in (502, 503, 504):
                    wait = self.config.retry_backoff_base ** attempt
                    logger.warning(
                        "MiroFish %d on %s — retry in %.1fs (attempt %d/%d)",
                        resp.status_code, path, wait,
                        attempt + 1, self.config.max_retries,
                    )
                    await asyncio.sleep(wait)
                    continue

                # Non-retryable error
                raise MiroFishAPIError(
                    resp.status_code, resp.text[:500], path
                )

            except httpx.TimeoutException as exc:
                last_exc = exc
                wait = self.config.retry_backoff_base ** attempt
                logger.warning(
                    "MiroFish timeout on %s — retry in %.1fs (attempt %d/%d)",
                    path, wait, attempt + 1, self.config.max_retries,
                )
                await asyncio.sleep(wait)
            except httpx.RequestError as exc:
                last_exc = exc
                wait = self.config.retry_backoff_base ** attempt
                logger.warning(
                    "MiroFish network error on %s: %s — retry in %.1fs (attempt %d/%d)",
                    path, exc, wait, attempt + 1, self.config.max_retries,
                )
                await asyncio.sleep(wait)
            except MiroFishAPIError:
                raise  # non-retryable — bubble up immediately

        # All retries exhausted
        raise MiroFishAPIError(
            0,
            f"All {self.config.max_retries} retries failed: {last_exc}",
            path,
        )

    # -- Public API ----------------------------------------------------------

    async def health_check(self) -> bool:
        """Return True if MiroFish backend is reachable."""
        try:
            client = await self._get_client()
            resp = await client.get(
                "/api/simulation/list",
                params={"limit": "1"},
                timeout=5.0,
            )
            return resp.status_code < 500
        except Exception:
            return False

    async def create_simulation(
        self,
        project_id: str,
        *,
        enable_twitter: bool = False,
        enable_reddit: bool = False,
    ) -> dict[str, Any]:
        """Create a new simulation.

        Returns dict with simulation_id and status.
        """
        return await self._request(
            "POST",
            "/api/simulation/create",
            json={
                "project_id": project_id,
                "enable_twitter": enable_twitter,
                "enable_reddit": enable_reddit,
            },
        )

    async def create_project(self, name: str, description: str = "") -> dict[str, Any]:
        """Create a MiroFish project (required before simulation)."""
        return await self._request(
            "POST",
            "/api/graph/ontology/generate",
            json={
                "simulation_requirement": description or name,
                "project_name": name,
            },
            timeout=self.config.long_timeout,
        )

    async def prepare_simulation(self, simulation_id: str) -> dict[str, Any]:
        """Prepare simulation (agent creation and environment setup)."""
        return await self._request(
            "POST",
            "/api/simulation/prepare",
            json={"simulation_id": simulation_id},
            timeout=self.config.long_timeout,
        )

    async def start_simulation(self, simulation_id: str) -> dict[str, Any]:
        """Start the simulation loop."""
        return await self._request(
            "POST",
            "/api/simulation/start",
            json={"simulation_id": simulation_id},
            timeout=self.config.long_timeout,
        )

    async def interview(
        self,
        simulation_id: str,
        agent_id: int,
        prompt: str,
        *,
        timeout: float = 60.0,
    ) -> dict[str, Any]:
        """Send a message to a specific agent and get their response.

        This is the core negotiation turn endpoint — user message goes in as
        the interview prompt, agent's negotiation response comes back.
        """
        return await self._request(
            "POST",
            "/api/simulation/interview",
            json={
                "simulation_id": simulation_id,
                "agent_id": agent_id,
                "prompt": prompt,
                "timeout": int(timeout),
            },
            timeout=self.config.long_timeout,
        )

    async def stop_simulation(self, simulation_id: str) -> dict[str, Any]:
        """Stop a running simulation."""
        return await self._request(
            "POST",
            "/api/simulation/stop",
            json={"simulation_id": simulation_id},
        )

    async def close_env(self, simulation_id: str) -> dict[str, Any]:
        """Close simulation environment gracefully."""
        return await self._request(
            "POST",
            "/api/simulation/close-env",
            json={"simulation_id": simulation_id},
        )

    async def get_status(self, simulation_id: str) -> dict[str, Any]:
        """Get current simulation status."""
        return await self._request(
            "GET",
            f"/api/simulation/{simulation_id}",
        )

    async def close(self) -> None:
        """Release the underlying httpx connection pool."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
