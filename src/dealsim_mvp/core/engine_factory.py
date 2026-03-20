"""
Engine factory for DealSim negotiation simulators.

Produces simulator instances based on engine name and configuration.
Supports per-session engine selection (routes pass the engine name)
with fallback chain: MiroFish → LLM → RuleBasedSimulator.

Engine names:
  - "rule_based"  → RuleBasedSimulator (always available, zero config)
  - "llm"         → LLMSimulator (requires LLM_API_KEY)
  - "mirofish"    → MiroFishSimulator (requires running MiroFish container)
  - "auto"        → best available engine (mirofish > llm > rule_based)
"""
from __future__ import annotations

import logging
import os
from typing import Literal

from dealsim_mvp.core.simulator import RuleBasedSimulator, SimulatorBase

logger = logging.getLogger(__name__)

EngineType = Literal["rule_based", "llm", "mirofish", "auto"]


def build_simulator(
    engine: EngineType = "auto",
    user_params: dict | None = None,
) -> SimulatorBase:
    """Build a simulator instance for the given engine type.

    Parameters
    ----------
    engine:
        Which engine to use. "auto" picks the best available.
    user_params:
        User-tweakable slider parameters (MiroFish only). Keys:
        market_pressure, patience, risk_tolerance, information_sharing,
        anchoring_strength — all 0-100 integers.

    Returns
    -------
    SimulatorBase
        Ready-to-use simulator. Always succeeds — falls back to
        RuleBasedSimulator if the requested engine is unavailable.
    """
    if engine == "auto":
        engine = _detect_best_engine()

    if engine == "mirofish":
        sim = _build_mirofish(user_params)
        if sim is not None:
            return sim
        logger.warning("MiroFish unavailable — trying LLM fallback")
        engine = "llm"

    if engine == "llm":
        sim = _build_llm()
        if sim is not None:
            return sim
        logger.warning("LLM unavailable — falling back to rule_based")

    logger.info("Engine: rule_based")
    return RuleBasedSimulator()


def _detect_best_engine() -> EngineType:
    """Detect the best available engine from environment."""
    # Check MiroFish first
    mf_url = os.environ.get("MIROFISH_BASE_URL", "").strip()
    if mf_url:
        return "mirofish"

    # Check LLM
    use_llm = os.environ.get("DEALSIM_USE_LLM", "false").lower() in (
        "1", "true", "yes",
    )
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if use_llm and api_key:
        return "llm"

    return "rule_based"


def _build_mirofish(user_params: dict | None = None) -> SimulatorBase | None:
    """Try to build a MiroFishSimulator. Returns None on failure.

    Performs a synchronous health probe to verify MiroFish is reachable.
    If the container is down, returns None immediately so the fallback
    chain selects the next engine. This prevents reporting MiroFish as
    active when only the env var is set but the container isn't running.
    """
    try:
        import asyncio
        from dealsim_mvp.core.mirofish_client import MiroFishClient
        from dealsim_mvp.core.mirofish_config import MiroFishConfig
        from dealsim_mvp.core.mirofish import MiroFishSimulator

        config = MiroFishConfig.from_env()
        client = MiroFishClient(config)

        # Quick health probe — fail fast if container is unreachable
        try:
            reachable = asyncio.run(client.health_check())
        except RuntimeError:
            # Already inside an event loop (e.g. FastAPI startup)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                reachable = pool.submit(
                    asyncio.run, client.health_check()
                ).result(timeout=10)

        if not reachable:
            logger.info(
                "MiroFish not reachable at %s — skipping", config.base_url,
            )
            asyncio.run(client.close()) if client._client else None
            return None

        fallback = RuleBasedSimulator()
        sim = MiroFishSimulator(
            client=client,
            fallback=fallback,
            user_params=user_params,
        )
        logger.info(
            "Engine: mirofish (base_url=%s, verified=True)", config.base_url,
        )
        return sim
    except Exception:
        logger.warning(
            "Failed to initialize MiroFishSimulator", exc_info=True,
        )
        return None


def _build_llm() -> SimulatorBase | None:
    """Try to build an LLMSimulator. Returns None on failure."""
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        from dealsim_mvp.core.llm_client import LLMClient, LLMConfig
        from dealsim_mvp.core.llm_simulator import LLMSimulator

        config = LLMConfig(
            api_key=api_key,
            base_url=os.environ.get(
                "LLM_BASE_URL", "https://api.deepseek.com/v1"
            ).strip(),
            model=os.environ.get("LLM_MODEL", "deepseek-chat").strip(),
            temperature=float(os.environ.get("LLM_TEMPERATURE", "0.7")),
            max_tokens=int(os.environ.get("LLM_MAX_TOKENS", "300")),
            timeout=int(os.environ.get("LLM_TIMEOUT", "30")),
        )
        client = LLMClient(config)
        fallback = RuleBasedSimulator()
        sim = LLMSimulator(client=client, fallback=fallback)
        logger.info(
            "Engine: llm (model=%s, base_url=%s)",
            config.model, config.base_url,
        )
        return sim
    except Exception:
        logger.warning(
            "Failed to initialize LLMSimulator", exc_info=True,
        )
        return None


def get_available_engines() -> list[str]:
    """Return list of engine names that could be built right now."""
    engines = ["rule_based"]  # always available

    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if api_key:
        engines.append("llm")

    mf_url = os.environ.get("MIROFISH_BASE_URL", "").strip()
    if mf_url:
        engines.append("mirofish")

    return engines
