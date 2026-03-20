"""
LLM-powered negotiation simulator.

Uses any OpenAI-compatible API to generate realistic opponent responses.
The persona's system_prompt defines the opponent's personality, constraints,
and negotiation strategy. Falls back to RuleBasedSimulator on any error.

Architecture mirrors MiroFishSimulator:
  - Sync public interface (generate_response / opening_statement) calls
    asyncio.run() internally so it satisfies SimulatorBase's sync contract.
  - Async variants (_async_generate / _async_opening) are exposed for
    FastAPI route handlers that are already inside an event loop.
  - Any exception from LLMClient triggers full fallback to RuleBasedSimulator
    for that turn — the caller always receives a valid Turn.

Unit convention: all monetary values share the persona's currency unit.
"""
from __future__ import annotations

import asyncio
import logging

from dealsim_mvp.core.llm_client import LLMClient
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

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Negotiation instructions appended to every persona system_prompt
# ---------------------------------------------------------------------------

_NEGOTIATION_INSTRUCTIONS = """
IMPORTANT RULES FOR YOUR RESPONSES:
1. Stay in character as the person described above. Never break character.
2. When making an offer, ALWAYS include a specific dollar amount.
3. Keep responses to 2-4 sentences max. Be conversational, not robotic.
4. If you decide to accept the user's offer, say "deal" or "agreed" clearly.
5. Never reveal your reservation price or hidden constraints directly.
6. React naturally to the user's tactics (questions, pressure, alternatives).
7. Format any dollar amounts as $XX,XXX (with dollar sign and commas).
"""

# Signals that indicate the LLM accepted the user's offer
_ACCEPTANCE_SIGNALS = (
    "deal", "agreed", "accept", "let's do it", "you've got a deal",
    "we have a deal", "works for me", "sounds good", "done",
)

# Signals that indicate the LLM is rejecting or walking away
_REJECTION_SIGNALS = (
    "can't do that", "no deal", "walk away", "not possible", "non-starter",
    "unfortunately", "cannot",
)


# ---------------------------------------------------------------------------
# Simulator
# ---------------------------------------------------------------------------

class LLMSimulator(SimulatorBase):
    """
    Negotiation simulator backed by an OpenAI-compatible LLM.

    Fallback contract:
      ANY exception from LLMClient triggers a full fallback to
      RuleBasedSimulator for that turn. The caller always receives a valid
      Turn; errors are logged at WARNING level.

    Concurrency note:
      generate_response and opening_statement are synchronous (matching the
      SimulatorBase contract). They call asyncio.run() internally. Use
      generate_response_async / opening_statement_async when already inside
      a running event loop (e.g., FastAPI route handlers).
    """

    def __init__(
        self,
        client: LLMClient,
        fallback: RuleBasedSimulator | None = None,
    ) -> None:
        self.client = client
        self.fallback = fallback or RuleBasedSimulator()

    def is_available(self) -> bool:
        """Return True if the LLM client has a valid API key configured."""
        return bool(self.client and self.client.config.api_key)

    # -- SimulatorBase interface -----------------------------------------

    def opening_statement(self, state: NegotiationState) -> Turn:
        """
        Generate opening statement via LLM; fall back to rule-based on error.

        Side effects (same as base class contract):
          - Sets state.opponent_last_offer and state.opponent_opening_anchor.
          - Appends the Turn to state.transcript.
        """
        try:
            return asyncio.run(self._async_opening(state))
        except Exception as exc:
            logger.warning(
                "LLM opening_statement failed (%s: %s) — rule-based fallback",
                type(exc).__name__, exc,
            )
            return self.fallback.opening_statement(state)

    def generate_response(
        self,
        state: NegotiationState,
        user_text: str,
    ) -> Turn:
        """
        Produce the opponent's next turn using the LLM.

        Contract (identical to RuleBasedSimulator):
          - Appends the user Turn to state.transcript before computing reply.
          - Returns the opponent Turn (SessionManager appends it).
          - Updates state fields (offers, concession counts) in place.

        On any LLM error, delegates the ENTIRE turn to RuleBasedSimulator
        (including user-turn append and state mutation) so state stays consistent.
        """
        try:
            return asyncio.run(self._async_generate(state, user_text))
        except Exception as exc:
            logger.warning(
                "LLM generate_response failed (%s: %s) — rule-based fallback",
                type(exc).__name__, exc,
            )
            return self.fallback.generate_response(state, user_text)

    # -- Async public variants (for FastAPI / already-running event loops) --

    async def opening_statement_async(self, state: NegotiationState) -> Turn:
        """Async variant of opening_statement for callers inside an event loop."""
        try:
            return await self._async_opening(state)
        except Exception as exc:
            logger.warning(
                "LLM opening_statement_async failed (%s: %s) — rule-based fallback",
                type(exc).__name__, exc,
            )
            return self.fallback.opening_statement(state)

    async def generate_response_async(
        self,
        state: NegotiationState,
        user_text: str,
    ) -> Turn:
        """Async variant of generate_response for callers inside an event loop."""
        try:
            return await self._async_generate(state, user_text)
        except Exception as exc:
            logger.warning(
                "LLM generate_response_async failed (%s: %s) — rule-based fallback",
                type(exc).__name__, exc,
            )
            return self.fallback.generate_response(state, user_text)

    # -- Async implementations -------------------------------------------

    async def _async_opening(self, state: NegotiationState) -> Turn:
        """
        Ask the LLM for its opening statement.

        Sends a single user message instructing the LLM to present its opening
        offer, then parses the response into a Turn.
        """
        persona = state.persona
        system_prompt = self._build_system_prompt(persona)

        opening_prompt = (
            f"You are starting a negotiation. Make your opening statement and "
            f"present your initial offer of ${persona.opening_offer:,.0f}. "
            f"Stay in character. Be natural and conversational."
        )

        text = await self.client.chat_completion(
            system_prompt,
            [{"role": "user", "content": opening_prompt}],
        )

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
        """
        Core async turn-generation logic.

        1. Classify and record the user's turn (same contract as RuleBasedSimulator).
        2. Build conversation history from transcript.
        3. Call the LLM.
        4. Parse the LLM response into a Move + offer.
        5. Update state and build the opponent Turn.
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

        # 2. Build conversation history (all turns BEFORE the one we just appended)
        system_prompt = self._build_system_prompt(state.persona)
        messages = self._build_message_history(state)

        # 3. LLM call
        response_text = await self.client.chat_completion(system_prompt, messages)

        # 4. Parse response
        move_type, offer = self._parse_llm_response(response_text, state)

        # 5. Update state
        prev_opponent_offer = state.opponent_last_offer
        if offer is not None:
            # Never reclassify an acceptance or rejection as a concession —
            # the accepted value is the user's last offer, not the opponent's.
            if (
                move_type not in (MoveType.ACCEPTANCE, MoveType.REJECTION)
                and prev_opponent_offer is not None
                and abs(offer - prev_opponent_offer) > 0.01
            ):
                state.opponent_total_concession += abs(offer - prev_opponent_offer)
                state.opponent_concession_count += 1
                move_type = MoveType.CONCESSION
            state.opponent_last_offer = offer

        if move_type == MoveType.ACCEPTANCE:
            state.resolved = True
            state.agreed_value = offer or state.user_last_offer or state.opponent_last_offer

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

    def _build_system_prompt(self, persona: NegotiationPersona) -> str:
        """Combine the persona's system_prompt with negotiation instructions."""
        base = persona.system_prompt or f"You are {persona.name}, {persona.role}."
        return base.rstrip() + "\n\n" + _NEGOTIATION_INSTRUCTIONS

    def _build_message_history(self, state: NegotiationState) -> list[dict[str, str]]:
        """
        Convert state.transcript to OpenAI message format.

        Skips the opening turn (turn_number 0) since that is covered by the
        system prompt. Only USER and OPPONENT turns are included.
        """
        messages: list[dict[str, str]] = []
        for turn in state.transcript:
            if turn.turn_number == 0:
                continue  # opening statement is implicit in system prompt context
            if turn.speaker == TurnSpeaker.USER:
                messages.append({"role": "user", "content": turn.text})
            elif turn.speaker == TurnSpeaker.OPPONENT:
                messages.append({"role": "assistant", "content": turn.text})
        return messages

    def _parse_llm_response(
        self,
        text: str,
        state: NegotiationState,
    ) -> tuple[MoveType, float | None]:
        """
        Extract MoveType and offer amount from the LLM's free-text response.

        Priority: acceptance > rejection > offer-based classification > question > unknown.
        Offer extraction delegates to _extract_offer (same regex as simulator.py).
        """
        offer = _extract_offer(text)
        lower = text.lower()

        # Acceptance: clear signal words with no new offer number
        if offer is None and any(s in lower for s in _ACCEPTANCE_SIGNALS):
            return MoveType.ACCEPTANCE, state.user_last_offer

        # Rejection: clear walkaway language with no counter-offer
        if offer is None and any(s in lower for s in _REJECTION_SIGNALS):
            return MoveType.REJECTION, None

        # Has an offer number — classify movement
        if offer is not None:
            prev = state.opponent_last_offer
            if prev is None:
                return MoveType.ANCHOR, offer
            if abs(offer - prev) < 1:
                return MoveType.COUNTER_OFFER, offer  # holding firm
            # Direction check: concession = moving toward user's position
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
