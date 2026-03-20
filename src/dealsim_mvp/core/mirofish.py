"""
MiroFish-powered negotiation simulator.

Uses the MiroFish multi-agent engine (running as a Docker container) to
generate realistic opponent responses. Communication is REST-only via the
interview endpoint — each user message is sent as an interview prompt and
the agent's response is the negotiation counter-move.

Architecture mirrors LLMSimulator exactly:
  - Sync public interface (generate_response / opening_statement) calls
    _run_async() internally so it satisfies SimulatorBase's sync contract.
  - Async variants are exposed for FastAPI route handlers already inside
    an event loop.
  - Any exception from MiroFishClient triggers full fallback to
    RuleBasedSimulator for that turn — the caller always receives a valid Turn.

AGPL-3.0 boundary: no MiroFish code is imported. All communication is REST.

Unit convention: all monetary values share the persona's currency unit.
"""
from __future__ import annotations

import asyncio
import logging
import re

from dealsim_mvp.core.mirofish_client import MiroFishClient, MiroFishAPIError
from dealsim_mvp.core.mirofish_config import MiroFishConfig
from dealsim_mvp.core.persona import NegotiationPersona
from dealsim_mvp.core.simulator import (
    MoveType,
    NegotiationState,
    RuleBasedSimulator,
    SimulatorBase,
    Turn,
    TurnSpeaker,
    _classify_user_move,
    _extract_offer,
    _update_state_from_user_move,
)

# Reuse _run_async from llm_simulator — same event-loop-safe helper
from dealsim_mvp.core.llm_simulator import _run_async

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Negotiation instructions prepended to the MiroFish agent prompt
# ---------------------------------------------------------------------------

_NEGOTIATION_INSTRUCTIONS = """
You are a negotiation opponent in a training simulation. Follow these rules:
1. Stay in character as the person described below. Never break character.
2. When making an offer, ALWAYS include a specific dollar amount.
3. Keep responses to 2-4 sentences max. Be conversational, not robotic.
4. If you decide to accept the user's offer, say "deal" or "agreed" clearly.
5. Never reveal your reservation price or hidden constraints directly.
6. React naturally to the user's tactics (questions, pressure, alternatives).
7. Format any dollar amounts as $XX,XXX (with dollar sign and commas).
"""

# Word-boundary regexes for parsing MiroFish agent responses (same as LLMSimulator)
_ACCEPTANCE_RE = re.compile(
    r'\b(?:' + '|'.join([
        r"deal", r"agreed", r"accept", r"let'?s do it", r"you'?ve got a deal",
        r"we have a deal", r"works for me", r"sounds good", r"done",
    ]) + r')\b',
    re.IGNORECASE,
)

_REJECTION_RE = re.compile(
    r'\b(?:' + '|'.join([
        r"can'?t do that", r"no deal", r"walk away", r"not possible",
        r"non-starter", r"unfortunately", r"cannot",
    ]) + r')\b',
    re.IGNORECASE,
)

# Negative patterns that override acceptance
_NOT_ACCEPTANCE_RE = re.compile(
    r'\b(?:not? done|far from done|not? agreed|don\'t accept|can\'t accept)\b',
    re.IGNORECASE,
)


class MiroFishSimulator(SimulatorBase):
    """
    Negotiation simulator backed by the MiroFish multi-agent engine.

    The simulator manages a single-agent MiroFish simulation where the agent
    is configured as a negotiation opponent. User messages are sent via the
    interview endpoint and agent responses are parsed into negotiation Turns.

    Fallback contract:
      ANY exception from MiroFishClient triggers a full fallback to
      RuleBasedSimulator for that turn. The caller always receives a valid
      Turn; errors are logged at WARNING level.

    Lifecycle:
      1. On first use (opening_statement), creates a MiroFish project +
         simulation with the persona's config.
      2. Each generate_response call sends the user message via interview.
      3. Session completion stops the simulation.
    """

    def __init__(
        self,
        client: MiroFishClient,
        fallback: RuleBasedSimulator | None = None,
        user_params: dict | None = None,
    ) -> None:
        self.client = client
        self.fallback = fallback or RuleBasedSimulator()
        self.user_params = user_params or {}

        # MiroFish session state — set during opening_statement
        self._simulation_id: str | None = None
        self._agent_id: int = 0
        self._initialized: bool = False
        self.__init_lock: asyncio.Lock | None = None

    @property
    def _init_lock(self) -> asyncio.Lock:
        """Lazily create asyncio.Lock inside the running event loop.

        Creating the lock at __init__ time (during synchronous startup)
        and using it inside an async context can cause RuntimeError in
        Python 3.12+ if the loop hasn't started yet.
        """
        if self.__init_lock is None:
            self.__init_lock = asyncio.Lock()
        return self.__init_lock

    def is_available(self) -> bool:
        """Return True if MiroFish backend is configured."""
        return bool(self.client and self.client.config.base_url)

    # -- SimulatorBase interface -----------------------------------------

    def opening_statement(self, state: NegotiationState) -> Turn:
        """Generate opening statement via MiroFish; fall back on error."""
        try:
            return _run_async(self._async_opening(state))
        except Exception as exc:
            logger.warning(
                "MiroFish opening_statement failed (%s: %s) — rule-based fallback",
                type(exc).__name__, exc,
            )
            return self.fallback.opening_statement(state)

    def generate_response(
        self,
        state: NegotiationState,
        user_text: str,
    ) -> Turn:
        """Produce the opponent's next turn using MiroFish.

        On any MiroFish error, delegates the ENTIRE turn to
        RuleBasedSimulator so state stays consistent.
        """
        try:
            return _run_async(self._async_generate(state, user_text))
        except Exception as exc:
            logger.warning(
                "MiroFish generate_response failed (%s: %s) — rule-based fallback",
                type(exc).__name__, exc,
            )
            return self.fallback.generate_response(state, user_text)

    # -- Async public variants -------------------------------------------

    async def opening_statement_async(self, state: NegotiationState) -> Turn:
        """Async variant for callers inside an event loop."""
        try:
            return await self._async_opening(state)
        except Exception as exc:
            logger.warning(
                "MiroFish opening_statement_async failed (%s: %s) — rule-based fallback",
                type(exc).__name__, exc,
            )
            return self.fallback.opening_statement(state)

    async def generate_response_async(
        self,
        state: NegotiationState,
        user_text: str,
    ) -> Turn:
        """Async variant for callers inside an event loop."""
        try:
            return await self._async_generate(state, user_text)
        except Exception as exc:
            logger.warning(
                "MiroFish generate_response_async failed (%s: %s) — rule-based fallback",
                type(exc).__name__, exc,
            )
            return self.fallback.generate_response(state, user_text)

    # -- Async implementations -------------------------------------------

    async def _ensure_simulation(self, persona: NegotiationPersona) -> None:
        """Create MiroFish project + simulation if not yet initialized.

        Uses persona.to_mirofish_config() to configure the agent with the
        full negotiation persona including constraints and system prompt.
        Serialized with asyncio.Lock to prevent duplicate simulation creation
        under concurrent requests.
        """
        if self._initialized:
            return

        async with self._init_lock:
            # Double-check after acquiring lock
            if self._initialized:
                return

            mf_config = persona.to_mirofish_config()
            project_name = f"dealsim-{persona.name.replace(' ', '-').lower()}"

            # Build the agent's system prompt with negotiation instructions
            # Inject personality and constraints from mf_config so MiroFish
            # receives the full persona, not just the name and role.
            system_prompt = _NEGOTIATION_INSTRUCTIONS.strip() + "\n\n"
            system_prompt += persona.system_prompt or (
                f"You are {persona.name}, {persona.role}."
            )
            personality = mf_config.get("personality", {})
            constraints = mf_config.get("constraints", {})
            if personality:
                system_prompt += (
                    f"\n\nPersonality: {personality.get('negotiation_style', 'neutral')} style, "
                    f"patience {personality.get('patience', 0.5):.1f}/1.0, "
                    f"transparency {personality.get('transparency', 0.5):.1f}/1.0."
                )
            if constraints:
                system_prompt += (
                    f"\nYour target: ${constraints.get('target', 0):,.0f}. "
                    f"Your absolute limit: ${constraints.get('reservation', 0):,.0f}. "
                    f"Start at: ${constraints.get('opening', 0):,.0f}."
                )
                hidden = constraints.get("hidden", [])
                if hidden:
                    system_prompt += f"\nHidden constraints: {'; '.join(hidden)}"

            # Apply user_params to the prompt if present
            if self.user_params:
                param_lines = []
                if "market_pressure" in self.user_params:
                    v = self.user_params["market_pressure"]
                    param_lines.append(
                        f"Market pressure level: {v}/100 "
                        f"({'high' if v > 70 else 'moderate' if v > 30 else 'low'})"
                    )
                if "patience" in self.user_params:
                    v = self.user_params["patience"]
                    param_lines.append(
                        f"Your patience level: {v}/100 "
                        f"({'very patient' if v > 70 else 'moderate' if v > 30 else 'impatient'})"
                    )
                if "risk_tolerance" in self.user_params:
                    v = self.user_params["risk_tolerance"]
                    param_lines.append(
                        f"Your risk tolerance: {v}/100 "
                        f"({'risk-seeking' if v > 70 else 'moderate' if v > 30 else 'risk-averse'})"
                    )
                if "information_sharing" in self.user_params:
                    v = self.user_params["information_sharing"]
                    param_lines.append(
                        f"How much you share: {v}/100 "
                        f"({'very open' if v > 70 else 'selective' if v > 30 else 'guarded'})"
                    )
                if "anchoring_strength" in self.user_params:
                    v = self.user_params["anchoring_strength"]
                    param_lines.append(
                        f"How firmly you anchor: {v}/100 "
                        f"({'very firm' if v > 70 else 'moderate' if v > 30 else 'flexible'})"
                    )
                if param_lines:
                    system_prompt += "\n\nBehavioral parameters:\n" + "\n".join(
                        f"- {line}" for line in param_lines
                    )

            # Create project with the negotiation scenario as the requirement
            description = (
                f"Negotiation simulation: {persona.name} ({persona.role}). "
                f"Style: {persona.style.value}. "
                f"Opening offer: ${persona.opening_offer:,.0f}."
            )
            project_resp = await self.client.create_project(
                name=project_name,
                description=description,
            )
            project_id = project_resp.get("data", project_resp).get(
                "project_id", ""
            )

            if not project_id:
                raise MiroFishAPIError(0, "No project_id in create response", "create_project")

            # Create simulation
            sim_resp = await self.client.create_simulation(project_id)
            sim_data = sim_resp.get("data", sim_resp)
            self._simulation_id = sim_data.get("simulation_id", "")

            if not self._simulation_id:
                raise MiroFishAPIError(0, "No simulation_id in create response", "create_simulation")

            # Prepare simulation (agent setup)
            await self.client.prepare_simulation(self._simulation_id)

            # Start simulation
            await self.client.start_simulation(self._simulation_id)

            self._initialized = True
            logger.info(
                "MiroFish simulation initialized: sim_id=%s, project_id=%s",
                self._simulation_id, project_id,
            )

    async def _async_opening(self, state: NegotiationState) -> Turn:
        """Ask MiroFish agent for its opening statement."""
        persona = state.persona
        await self._ensure_simulation(persona)

        opening_prompt = (
            f"You are starting a negotiation. Make your opening statement and "
            f"present your initial offer of ${persona.opening_offer:,.0f}. "
            f"Stay in character. Be natural and conversational."
        )

        resp = await self.client.interview(
            self._simulation_id,
            agent_id=self._agent_id,
            prompt=opening_prompt,
        )

        # Extract response text from MiroFish interview response
        text = self._extract_response_text(resp)

        offer = _extract_offer(text) or persona.opening_offer
        state.opponent_last_offer = offer
        state.opponent_opening_anchor = offer

        turn = Turn(
            turn_number=0,
            speaker=TurnSpeaker.OPPONENT,
            text=text,
            move_type=MoveType.ANCHOR,
            offer_amount=offer,
        )
        state.transcript.append(turn)
        return turn

    async def _async_generate(
        self,
        state: NegotiationState,
        user_text: str,
    ) -> Turn:
        """Core async turn-generation logic.

        1. Classify and record the user's turn.
        2. Send user message to MiroFish agent via interview.
        3. Parse the agent response into a Move + offer.
        4. Update state and build the opponent Turn.
        """
        state.turn_count += 1
        turn_n = state.turn_count * 2  # user = odd, opponent = even

        # 1. Record user turn
        user_move, user_offer = _classify_user_move(user_text, state)
        user_turn = Turn(
            turn_number=turn_n - 1,
            speaker=TurnSpeaker.USER,
            text=user_text,
            move_type=user_move,
            offer_amount=user_offer,
            concession_from=(
                state.user_last_offer
                if user_move == MoveType.CONCESSION
                else None
            ),
        )
        state.transcript.append(user_turn)
        _update_state_from_user_move(state, user_move, user_offer)

        # 2. Send to MiroFish
        await self._ensure_simulation(state.persona)
        resp = await self.client.interview(
            self._simulation_id,
            agent_id=self._agent_id,
            prompt=user_text,
        )
        response_text = self._extract_response_text(resp)

        # 3. Parse response
        move_type, offer = self._parse_response(response_text, state)

        # 4. Update state
        prev_opponent_offer = state.opponent_last_offer
        if offer is not None:
            if (
                move_type not in (MoveType.ACCEPTANCE, MoveType.REJECTION)
                and prev_opponent_offer is not None
                and abs(offer - prev_opponent_offer) > 0.01
            ):
                state.opponent_total_concession += abs(
                    offer - prev_opponent_offer
                )
                state.opponent_concession_count += 1
                move_type = MoveType.CONCESSION
            state.opponent_last_offer = offer

        if move_type == MoveType.ACCEPTANCE:
            state.resolved = True
            state.agreed_value = (
                offer or state.user_last_offer or state.opponent_last_offer
            )

        opp_turn = Turn(
            turn_number=turn_n,
            speaker=TurnSpeaker.OPPONENT,
            text=response_text,
            move_type=move_type,
            offer_amount=offer,
            concession_from=(
                prev_opponent_offer
                if move_type == MoveType.CONCESSION
                else None
            ),
        )
        state.transcript.append(opp_turn)
        return opp_turn

    # -- Helpers ---------------------------------------------------------

    def _extract_response_text(self, resp: dict) -> str:
        """Extract the agent's text response from MiroFish interview result.

        MiroFish interview responses have varying structures depending on
        single vs dual platform mode. We handle both.
        """
        data = resp.get("data", resp)

        # Single platform: data.result.response
        result = data.get("result", {})
        if isinstance(result, dict):
            # Direct response field
            if "response" in result:
                return result["response"]
            # Dual platform: result.platforms.<platform>.response
            platforms = result.get("platforms", {})
            for platform_data in platforms.values():
                if isinstance(platform_data, dict) and "response" in platform_data:
                    return platform_data["response"]

        # Fallback: try top-level response
        if "response" in data:
            return data["response"]

        # Unrecognizable format — raise so the fallback chain kicks in.
        # Never show raw Python dict repr to the user.
        raise MiroFishAPIError(
            0,
            f"Unrecognizable response format: {str(resp)[:200]}",
            "/interview",
        )

    def _parse_response(
        self,
        text: str,
        state: NegotiationState,
    ) -> tuple[MoveType, float | None]:
        """Extract MoveType and offer from the agent's free-text response.

        Same classification logic as LLMSimulator._parse_llm_response.
        """
        offer = _extract_offer(text)

        # Acceptance
        if offer is None and _ACCEPTANCE_RE.search(text) and not _NOT_ACCEPTANCE_RE.search(text):
            return MoveType.ACCEPTANCE, state.user_last_offer

        # Rejection
        if offer is None and _REJECTION_RE.search(text):
            return MoveType.REJECTION, None

        # Has an offer number
        if offer is not None:
            prev = state.opponent_last_offer
            if prev is None:
                return MoveType.ANCHOR, offer
            if abs(offer - prev) < 1:
                return MoveType.COUNTER_OFFER, offer
            persona = state.persona
            toward_user = (
                offer > prev
                if persona.reservation_price > persona.opening_offer
                else offer < prev
            )
            if toward_user:
                return MoveType.CONCESSION, offer
            return MoveType.COUNTER_OFFER, offer

        # No number — question or general statement
        if "?" in text:
            return MoveType.QUESTION, None

        return MoveType.INFORMATION_SHARE, None

    async def cleanup(self) -> None:
        """Stop the MiroFish simulation and close the client.

        Teardown order mirrors startup in reverse: stop loop first,
        then close environment, then release HTTP connection pool.
        """
        if self._simulation_id:
            try:
                await self.client.stop_simulation(self._simulation_id)
            except Exception:
                logger.debug("Failed to stop MiroFish sim", exc_info=True)
            try:
                await self.client.close_env(self._simulation_id)
            except Exception:
                logger.debug("Failed to close MiroFish env", exc_info=True)
        await self.client.close()
