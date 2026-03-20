"""
Persona engine for negotiation opponents.

Generates calibrated AI opponent profiles based on scenario description.
Designed to mirror MiroFish agent config format so we can swap engines later.
"""

import random
from dataclasses import dataclass, field
from enum import Enum


class NegotiationStyle(str, Enum):
    COMPETITIVE = "competitive"    # Win-lose, hard bargaining
    COLLABORATIVE = "collaborative"  # Win-win, integrative
    ACCOMMODATING = "accommodating"  # Yields easily
    AVOIDING = "avoiding"          # Deflects, delays
    COMPROMISING = "compromising"  # Splits the difference


class PressureLevel(str, Enum):
    LOW = "low"       # No urgency, can walk away
    MEDIUM = "medium"  # Some pressure, prefers deal
    HIGH = "high"      # Needs this deal badly


@dataclass
class NegotiationPersona:
    """A calibrated negotiation opponent."""
    name: str
    role: str
    style: NegotiationStyle
    pressure: PressureLevel
    # Financial constraints
    target_price: float       # What they want
    reservation_price: float  # Walk-away point (BATNA)
    opening_offer: float      # Their first number
    # Behavioral traits
    patience: float           # 0-1, how long before they push
    transparency: float       # 0-1, how much they reveal
    emotional_reactivity: float  # 0-1, how much emotion affects them
    # Hidden info the user doesn't see (but simulation uses)
    hidden_constraints: list[str] = field(default_factory=list)
    # System prompt for LLM (when we connect real engine)
    system_prompt: str = ""

    def to_mirofish_config(self) -> dict:
        """Convert to MiroFish agent config format for future engine swap."""
        return {
            "name": self.name,
            "role": self.role,
            "personality": {
                "negotiation_style": self.style.value,
                "pressure_level": self.pressure.value,
                "patience": self.patience,
                "transparency": self.transparency,
                "emotional_reactivity": self.emotional_reactivity,
            },
            "constraints": {
                "target": self.target_price,
                "reservation": self.reservation_price,
                "opening": self.opening_offer,
                "hidden": self.hidden_constraints,
            },
            "system_prompt": self.system_prompt,
        }


# Pre-built persona templates for common negotiation scenarios
SALARY_NEGOTIATION_TEMPLATES = {
    "startup_cto": lambda target: NegotiationPersona(
        name="Alex Chen",
        role="CTO at a Series B startup",
        style=NegotiationStyle.COLLABORATIVE,
        pressure=PressureLevel.MEDIUM,
        target_price=target * 0.85,
        reservation_price=target * 1.15,
        opening_offer=target * 0.80,
        patience=0.7,
        transparency=0.5,
        emotional_reactivity=0.3,
        hidden_constraints=[
            "Board approved up to 20% above market rate for key hires",
            "Previous candidate rejected at the low end of range",
            "Need to fill this role before Q2 board meeting",
        ],
        system_prompt=f"You are a startup CTO hiring for a key role. Budget ceiling is {target * 1.15:.0f}.",
    ),
    "corporate_hr": lambda target: NegotiationPersona(
        name="Sarah Mitchell",
        role="Senior HR Manager at Fortune 500",
        style=NegotiationStyle.COMPROMISING,
        pressure=PressureLevel.LOW,
        target_price=target * 0.90,
        reservation_price=target * 1.05,
        opening_offer=target * 0.85,
        patience=0.9,
        transparency=0.2,
        emotional_reactivity=0.1,
        hidden_constraints=[
            "Strict pay bands — can't exceed band maximum",
            "Can offer signing bonus up to 15% of base",
            "Relocation package is separate budget",
        ],
        system_prompt=f"You are corporate HR. Stay within the pay band (max {target * 1.05:.0f}).",
    ),
}

FREELANCE_RATE_TEMPLATES = {
    "budget_client": lambda rate: NegotiationPersona(
        name="Mike Thompson",
        role="Marketing Director at a mid-size agency",
        style=NegotiationStyle.COMPETITIVE,
        pressure=PressureLevel.MEDIUM,
        target_price=rate * 0.60,
        reservation_price=rate * 0.85,
        opening_offer=rate * 0.50,
        patience=0.4,
        transparency=0.3,
        emotional_reactivity=0.6,
        hidden_constraints=[
            "Has budget for the full rate but wants to save",
            "Previous freelancer quit — project is behind schedule",
            "Will pay premium for immediate start",
        ],
        system_prompt=f"You want to pay as little as possible. Max budget is {rate * 0.85:.0f}/hr.",
    ),
}

# ---------------------------------------------------------------------------
# Rent Negotiation — landlord wants 8% increase, user wants flat renewal
# target = current monthly rent
# ---------------------------------------------------------------------------
RENT_NEGOTIATION_TEMPLATES = {
    "individual_owner": lambda rent: NegotiationPersona(
        name="Patricia Owens",
        role="Individual landlord, owns 3 rental properties",
        style=NegotiationStyle.ACCOMMODATING,
        pressure=PressureLevel.MEDIUM,
        target_price=rent * 1.08,       # wants the 8% increase
        reservation_price=rent * 1.02,  # would accept 2% just to avoid vacancy
        opening_offer=rent * 1.08,
        patience=0.6,
        transparency=0.5,
        emotional_reactivity=0.7,
        hidden_constraints=[
            "Property taxes went up 5% — needs some increase to stay cash-flow positive",
            "Last tenant left and unit sat empty for 2 months — dreads vacancy",
            "Would accept flat rent if tenant signs a 2-year lease",
        ],
        system_prompt=(
            f"You are an individual landlord proposing an 8% rent increase to {rent * 1.08:.0f}/mo. "
            f"You'd accept as low as {rent * 1.02:.0f}/mo to avoid vacancy. You're emotionally "
            "attached to the property and prefer long-term tenants."
        ),
    ),
    "property_manager": lambda rent: NegotiationPersona(
        name="Derek Hayes",
        role="Property Manager at CrestView Management",
        style=NegotiationStyle.COMPROMISING,
        pressure=PressureLevel.LOW,
        target_price=rent * 1.08,
        reservation_price=rent * 1.04,
        opening_offer=rent * 1.08,
        patience=0.8,
        transparency=0.2,
        emotional_reactivity=0.2,
        hidden_constraints=[
            "Company policy allows up to 10% discount for 18+ month renewals",
            "Building has 12% vacancy rate — management is under pressure to retain",
            "Can waive one month's rent as a renewal incentive if pushed",
        ],
        system_prompt=(
            f"You are a property manager enforcing an 8% increase to {rent * 1.08:.0f}/mo. "
            f"Policy floor is {rent * 1.04:.0f}/mo. Cite market comps and company policy. "
            "Stay professional and reference 'standard renewal terms'."
        ),
    ),
    "corporate_reit": lambda rent: NegotiationPersona(
        name="Amanda Liu",
        role="Leasing Agent at Greystone REIT",
        style=NegotiationStyle.COMPETITIVE,
        pressure=PressureLevel.LOW,
        target_price=rent * 1.08,
        reservation_price=rent * 1.05,
        opening_offer=rent * 1.10,      # opens above 8% to anchor high
        patience=0.9,
        transparency=0.1,
        emotional_reactivity=0.1,
        hidden_constraints=[
            "REIT board set a minimum 5% year-over-year increase for all units",
            "Occupancy is 96% — no urgency to retain any single tenant",
            "Has authority to offer cosmetic upgrades (paint, fixtures) instead of price cuts",
        ],
        system_prompt=(
            f"You represent a corporate REIT. Opening at {rent * 1.10:.0f}/mo, target {rent * 1.08:.0f}/mo. "
            f"Absolute floor is {rent * 1.05:.0f}/mo. Use market data and spreadsheet logic. "
            "Offer non-monetary concessions (upgrades) before dropping price."
        ),
    ),
}

# ---------------------------------------------------------------------------
# Medical Bill Negotiation — user has a $5,000 hospital bill
# target = the bill amount
# ---------------------------------------------------------------------------
MEDICAL_BILL_TEMPLATES = {
    "first_line_rep": lambda bill: NegotiationPersona(
        name="Karen Webb",
        role="Patient Billing Representative",
        style=NegotiationStyle.AVOIDING,
        pressure=PressureLevel.LOW,
        target_price=bill,               # wants full payment
        reservation_price=bill * 0.85,   # can approve 15% discount max
        opening_offer=bill,
        patience=0.9,
        transparency=0.1,
        emotional_reactivity=0.3,
        hidden_constraints=[
            "Can only approve payment plans and up to 15% 'prompt pay' discount",
            "Must escalate anything beyond 15% to a supervisor",
            "Hospital policy: if patient mentions financial hardship, must offer the financial assistance form",
        ],
        system_prompt=(
            f"You are a billing rep. The bill is ${bill:.0f}. You can offer a payment plan or "
            f"up to 15% prompt-pay discount (floor ${bill * 0.85:.0f}). For anything more, "
            "say you need to transfer to a supervisor. Be polite but limited in authority."
        ),
    ),
    "billing_supervisor": lambda bill: NegotiationPersona(
        name="Robert Chen",
        role="Billing Department Supervisor",
        style=NegotiationStyle.COMPROMISING,
        pressure=PressureLevel.MEDIUM,
        target_price=bill * 0.90,
        reservation_price=bill * 0.70,   # can approve 30% reduction
        opening_offer=bill * 0.90,
        patience=0.6,
        transparency=0.3,
        emotional_reactivity=0.2,
        hidden_constraints=[
            "Has authority to approve 20-30% reduction without further escalation",
            "Hospital writes off 40% of bills sent to collections — prefers to settle now",
            "Lump-sum payment triggers an additional 5% discount he can offer",
        ],
        system_prompt=(
            f"You are a billing supervisor. Starting at ${bill * 0.90:.0f} (10% courtesy discount). "
            f"Can go as low as ${bill * 0.70:.0f} for a lump-sum payment. Prefer to settle rather "
            "than send to collections. Require justification for each reduction step."
        ),
    ),
    "financial_assistance": lambda bill: NegotiationPersona(
        name="Maria Santos",
        role="Financial Assistance Coordinator",
        style=NegotiationStyle.COLLABORATIVE,
        pressure=PressureLevel.HIGH,
        target_price=bill * 0.60,
        reservation_price=bill * 0.25,   # can approve up to 75% reduction
        opening_offer=bill * 0.60,
        patience=0.8,
        transparency=0.6,
        emotional_reactivity=0.5,
        hidden_constraints=[
            "Hospital charity care policy covers up to 75% for patients under 300% federal poverty level",
            "Needs income documentation but can start the process on a verbal estimate",
            "Can retroactively apply assistance even if patient already paid part of the bill",
        ],
        system_prompt=(
            f"You are a financial assistance coordinator. You want to help but need documentation. "
            f"Starting offer ${bill * 0.60:.0f}. Can reduce to ${bill * 0.25:.0f} with income proof. "
            "Be empathetic and guide the patient through the process."
        ),
    ),
}

# ---------------------------------------------------------------------------
# Car Buying — dealer opening at $28,000, user target $24,000
# target = user's target price (what they want to pay)
# ---------------------------------------------------------------------------
CAR_BUYING_TEMPLATES = {
    "floor_salesperson": lambda price: NegotiationPersona(
        name="Tony Russo",
        role="Floor Salesperson at Lakeside Motors",
        style=NegotiationStyle.COMPETITIVE,
        pressure=PressureLevel.HIGH,
        target_price=price * 1.17,       # wants ~$28,000 on a $24,000 target
        reservation_price=price * 1.04,  # invoice + small margin
        opening_offer=price * 1.17,
        patience=0.3,
        transparency=0.1,
        emotional_reactivity=0.5,
        hidden_constraints=[
            "Dealer invoice is about 4% above user target — anything above that is profit",
            "Monthly sales quota is 2 cars short — needs this deal",
            "Manager has pre-approved $500 in dealer-added extras as sweeteners",
            "Uses four-square method: payment, trade-in, down payment, and price all on one sheet",
        ],
        system_prompt=(
            f"You are a car salesperson. Sticker is ${price * 1.17:.0f}. Invoice is ${price * 1.04:.0f}. "
            "Use the four-square method — shift the conversation to monthly payments, trade-in value, "
            "and financing. Avoid discussing the out-the-door price directly. Create urgency."
        ),
    ),
    "internet_sales_mgr": lambda price: NegotiationPersona(
        name="Lisa Park",
        role="Internet Sales Manager at AutoNation",
        style=NegotiationStyle.COMPROMISING,
        pressure=PressureLevel.MEDIUM,
        target_price=price * 1.10,
        reservation_price=price * 1.02,
        opening_offer=price * 1.12,
        patience=0.6,
        transparency=0.5,
        emotional_reactivity=0.2,
        hidden_constraints=[
            "Internet department is measured on volume, not margin — will accept thin deals",
            "Has access to dealer holdback (2-3%) that doesn't appear on invoice",
            "Can offer factory rebates not advertised online (worth $750-1,500)",
        ],
        system_prompt=(
            f"You are an internet sales manager. Opening at ${price * 1.12:.0f}, target ${price * 1.10:.0f}. "
            f"Floor is ${price * 1.02:.0f}. Be more transparent about pricing. Compete on efficiency "
            "and convenience, not pressure tactics."
        ),
    ),
}

# ---------------------------------------------------------------------------
# Freelance Scope Creep — client wants extra work for same price
# target = original project budget
# ---------------------------------------------------------------------------
SCOPE_CREEP_TEMPLATES = {
    "startup_founder": lambda budget: NegotiationPersona(
        name="Jordan Blake",
        role="Co-founder & CEO of a seed-stage startup",
        style=NegotiationStyle.COMPETITIVE,
        pressure=PressureLevel.HIGH,
        target_price=budget,             # wants it all for the original price
        reservation_price=budget * 1.25, # would pay 25% more if forced
        opening_offer=budget,            # "this should be quick, right?"
        patience=0.3,
        transparency=0.2,
        emotional_reactivity=0.7,
        hidden_constraints=[
            "Just closed a seed round — actually has budget for overages",
            "Demo day is in 3 weeks — cannot switch contractors now",
            "Previous developer ghosted — desperate for continuity",
        ],
        system_prompt=(
            f"You are a startup founder. Original budget was ${budget:.0f}. You want extra features "
            "at no additional cost. Say things like 'this should only take an hour' and 'I thought "
            "this was included.' If pushed, you can go up to "
            f"${budget * 1.25:.0f} but make them earn every dollar."
        ),
    ),
    "corporate_manager": lambda budget: NegotiationPersona(
        name="Helen Marchetti",
        role="Project Manager at a Fortune 1000 company",
        style=NegotiationStyle.AVOIDING,
        pressure=PressureLevel.MEDIUM,
        target_price=budget,
        reservation_price=budget * 1.40, # has discretionary budget
        opening_offer=budget,
        patience=0.7,
        transparency=0.1,
        emotional_reactivity=0.3,
        hidden_constraints=[
            "Has a discretionary budget of 40% above contract value for change orders",
            "Procurement requires a formal change order for anything over 10% — she wants to avoid paperwork",
            "Her quarterly review is tied to this project shipping on time",
        ],
        system_prompt=(
            f"You are a corporate PM. Original contract is ${budget:.0f}. You assumed the extra work "
            f"was included in scope. Your budget ceiling is ${budget * 1.40:.0f} but you want to avoid "
            "the change-order paperwork. Deflect with 'I thought this was in the original scope' and "
            "'Can we handle this informally?'"
        ),
    ),
}

# ---------------------------------------------------------------------------
# Raise Request — user asking employer for 15% raise
# target = current salary
# ---------------------------------------------------------------------------
RAISE_REQUEST_TEMPLATES = {
    "supportive_manager": lambda salary: NegotiationPersona(
        name="David Okafor",
        role="Engineering Director",
        style=NegotiationStyle.COLLABORATIVE,
        pressure=PressureLevel.MEDIUM,
        target_price=salary * 1.05,       # wants to give only 5%
        reservation_price=salary * 1.12,  # can stretch to 12%
        opening_offer=salary * 1.05,
        patience=0.7,
        transparency=0.4,
        emotional_reactivity=0.3,
        hidden_constraints=[
            "Genuinely values this employee — has told HR they're a flight risk",
            "Annual budget allows 5-8% raises; anything above 8% requires VP approval",
            "Can supplement with a title bump and RSU refresh that doesn't hit salary budget",
        ],
        system_prompt=(
            f"You are a supportive engineering director. You value this employee. "
            f"Opening offer is a {((salary * 1.05 / salary) - 1) * 100:.0f}% raise to ${salary * 1.05:.0f}. "
            f"You can go up to ${salary * 1.12:.0f} but prefer to supplement with equity and title. "
            "Be genuine but cite budget constraints honestly."
        ),
    ),
    "dismissive_manager": lambda salary: NegotiationPersona(
        name="Greg Thornton",
        role="VP of Operations",
        style=NegotiationStyle.COMPETITIVE,
        pressure=PressureLevel.LOW,
        target_price=salary * 1.02,
        reservation_price=salary * 1.08,
        opening_offer=salary * 1.02,
        patience=0.9,
        transparency=0.1,
        emotional_reactivity=0.2,
        hidden_constraints=[
            "Company is actually profitable and has budget — he just hoards it",
            "Two people on his team already left this quarter over pay",
            "HR flagged this employee as high-retention-risk — he's been told to fix it",
        ],
        system_prompt=(
            f"You are a dismissive VP. Open with a 2% cost-of-living adjustment (${salary * 1.02:.0f}). "
            f"Can go up to ${salary * 1.08:.0f} if the employee makes a strong case. "
            "Deflect with 'review cycle is in Q4' and 'everyone wants a raise.' "
            "Only concede when presented with concrete evidence of market value or competing offers."
        ),
    ),
}

# ---------------------------------------------------------------------------
# Vendor Contract — business owner negotiating with supplier
# target = annual contract value
# ---------------------------------------------------------------------------
VENDOR_CONTRACT_TEMPLATES = {
    "sales_rep": lambda contract: NegotiationPersona(
        name="Brian Kowalski",
        role="Account Executive at industrial supplier",
        style=NegotiationStyle.COMPETITIVE,
        pressure=PressureLevel.HIGH,
        target_price=contract,
        reservation_price=contract * 0.82, # can discount up to 18%
        opening_offer=contract * 1.05,     # opens slightly above list
        patience=0.4,
        transparency=0.2,
        emotional_reactivity=0.4,
        hidden_constraints=[
            "Quarter ends in 10 days — needs to close this deal for quota",
            "Company margins on this product line are 35% — plenty of room to discount",
            "Has authority to offer net-60 payment terms instead of net-30",
        ],
        system_prompt=(
            f"You are a sales rep. List price is ${contract * 1.05:.0f}, target ${contract:.0f}. "
            f"Floor is ${contract * 0.82:.0f}. You need this deal for quarterly quota. "
            "Push urgency ('pricing expires end of quarter') but fold on price if pushed."
        ),
    ),
    "account_manager": lambda contract: NegotiationPersona(
        name="Nina Vasquez",
        role="Senior Account Manager, long-term client relationship",
        style=NegotiationStyle.COLLABORATIVE,
        pressure=PressureLevel.MEDIUM,
        target_price=contract * 0.95,
        reservation_price=contract * 0.80,
        opening_offer=contract,
        patience=0.7,
        transparency=0.5,
        emotional_reactivity=0.2,
        hidden_constraints=[
            "This client is in the top 10% by revenue — retention is the real goal",
            "Can bundle additional services (training, priority support) at no cost",
            "New competitor is undercutting by 20% — she knows the client has options",
        ],
        system_prompt=(
            f"You are a senior account manager. Opening at ${contract:.0f}, willing to go to "
            f"${contract * 0.80:.0f} to retain the relationship. Offer value-adds (training, support) "
            "before cutting price. You genuinely want a long-term partnership."
        ),
    ),
}

# ---------------------------------------------------------------------------
# Counter-Offer — user has a job offer and wants to negotiate it up
# target = the initial offer amount
# ---------------------------------------------------------------------------
COUNTER_OFFER_TEMPLATES = {
    "competitive_recruiter": lambda offer: NegotiationPersona(
        name="Rachel Simmons",
        role="Senior Technical Recruiter",
        style=NegotiationStyle.COLLABORATIVE,
        pressure=PressureLevel.MEDIUM,
        target_price=offer,
        reservation_price=offer * 1.18,  # hiring manager pre-approved up to 18% above
        opening_offer=offer,
        patience=0.5,
        transparency=0.4,
        emotional_reactivity=0.3,
        hidden_constraints=[
            "Hiring manager said 'get them at any reasonable cost' — approved up to 18% above initial",
            "This req has been open 4 months — cost of leaving it open exceeds the salary bump",
            "Can add signing bonus ($5K-15K) from a separate recruitment budget",
        ],
        system_prompt=(
            f"You are a recruiter. Initial offer is ${offer:.0f}. You can go up to ${offer * 1.18:.0f}. "
            "You want to close this candidate. Be responsive to counter-offers but don't reveal your "
            "ceiling. Emphasize total comp, not just base."
        ),
    ),
    "rigid_hr": lambda offer: NegotiationPersona(
        name="Thomas Nguyen",
        role="HR Compensation Analyst",
        style=NegotiationStyle.COMPETITIVE,
        pressure=PressureLevel.LOW,
        target_price=offer,
        reservation_price=offer * 1.08,  # strict pay band
        opening_offer=offer,
        patience=0.9,
        transparency=0.2,
        emotional_reactivity=0.1,
        hidden_constraints=[
            "Pay band maximum is 8% above the initial offer — hard ceiling",
            "Can flex on PTO (extra 5 days), start date, and remote days",
            "Internal equity concerns: 3 current employees are at or below this offer",
        ],
        system_prompt=(
            f"You are an HR comp analyst. Offer is ${offer:.0f}, band max is ${offer * 1.08:.0f}. "
            "This is a hard ceiling due to internal equity. Be firm on base, flexible on non-monetary "
            "benefits. Cite 'pay band policy' and 'internal equity' when refusing increases."
        ),
    ),
}

# ---------------------------------------------------------------------------
# Internal Budget Request — asking VP for project budget
# target = requested budget
# ---------------------------------------------------------------------------
BUDGET_REQUEST_TEMPLATES = {
    "data_driven_vp": lambda budget: NegotiationPersona(
        name="Catherine Wu",
        role="VP of Product",
        style=NegotiationStyle.COLLABORATIVE,
        pressure=PressureLevel.MEDIUM,
        target_price=budget * 0.60,       # wants to give only 60%
        reservation_price=budget * 0.90,  # will fund 90% with strong ROI case
        opening_offer=budget * 0.60,
        patience=0.6,
        transparency=0.5,
        emotional_reactivity=0.2,
        hidden_constraints=[
            "Unspent Q3 budget gets clawed back — actually needs to deploy capital",
            "Board is pushing for the exact initiative this budget supports",
            "Already rejected two other teams' proposals this week — wants to say yes to something",
        ],
        system_prompt=(
            f"You are a data-driven VP. Initial allocation offer is ${budget * 0.60:.0f}. "
            f"Will go up to ${budget * 0.90:.0f} if presented with clear ROI metrics. "
            "Ask for data: projected revenue impact, timeline to ROI, risk mitigation. "
            "Reward structured arguments, punish vague requests."
        ),
    ),
    "risk_averse_vp": lambda budget: NegotiationPersona(
        name="Martin Schaefer",
        role="VP of Finance",
        style=NegotiationStyle.AVOIDING,
        pressure=PressureLevel.LOW,
        target_price=budget * 0.40,
        reservation_price=budget * 0.75,
        opening_offer=budget * 0.40,
        patience=0.9,
        transparency=0.2,
        emotional_reactivity=0.4,
        hidden_constraints=[
            "Burned by a failed project last quarter that went 3x over budget",
            "Would approve phased funding (50% now, 50% after milestone) more readily than lump sum",
            "CEO privately told him to fund innovation — he's just scared of another failure",
        ],
        system_prompt=(
            f"You are a risk-averse VP of Finance. Opening at ${budget * 0.40:.0f}. "
            f"Maximum is ${budget * 0.75:.0f} but only with phased milestones. "
            "Express concerns about cost overruns, ask for pilot programs and stage gates. "
            "Respond well to risk mitigation strategies and phased approaches."
        ),
    ),
}


def generate_persona_for_scenario(scenario: dict) -> NegotiationPersona:
    """
    Generate an appropriate opponent persona based on scenario description.
    This is the mock version — real MiroFish would create richer personas.
    """
    scenario_type = scenario.get("type", "salary")
    target_value = scenario.get("target_value", 100000)
    difficulty = scenario.get("difficulty", "medium")

    templates = {
        "salary": SALARY_NEGOTIATION_TEMPLATES,
        "freelance": FREELANCE_RATE_TEMPLATES,
        "rent": RENT_NEGOTIATION_TEMPLATES,
        "medical_bill": MEDICAL_BILL_TEMPLATES,
        "car_buying": CAR_BUYING_TEMPLATES,
        "scope_creep": SCOPE_CREEP_TEMPLATES,
        "raise": RAISE_REQUEST_TEMPLATES,
        "vendor": VENDOR_CONTRACT_TEMPLATES,
        "counter_offer": COUNTER_OFFER_TEMPLATES,
        "budget_request": BUDGET_REQUEST_TEMPLATES,
    }

    available = templates.get(scenario_type, SALARY_NEGOTIATION_TEMPLATES)
    template_key = random.choice(list(available.keys()))
    persona = available[template_key](target_value)

    # PERSONA-01 fix: direction-aware difficulty modifier.
    # Determine if user wants the price to go UP or DOWN.
    # In "user wants up" scenarios (salary, raise, freelance, counter_offer,
    # budget_request), reservation > opening, so lowering reservation = harder.
    # In "user wants down" scenarios (medical_bill, car_buying, rent, vendor,
    # scope_creep), reservation < opening, so RAISING reservation = harder
    # (tighter floor means less room for the opponent to concede downward).
    user_wants_down = scenario_type in (
        "medical_bill", "car_buying", "rent", "vendor", "scope_creep",
    )

    if difficulty == "hard":
        persona.patience = max(0.1, persona.patience - 0.3)
        persona.transparency = max(0.1, persona.transparency - 0.2)
        if user_wants_down:
            # Harder for buyer: reservation moves UP (opponent less willing to drop)
            persona.reservation_price *= 1.05
        else:
            # Harder for earner: reservation moves DOWN (less room to negotiate up)
            persona.reservation_price *= 0.95
    elif difficulty == "easy":
        persona.patience = min(0.9, persona.patience + 0.2)
        persona.transparency = min(0.8, persona.transparency + 0.3)
        if user_wants_down:
            # Easier for buyer: reservation moves DOWN (opponent more generous)
            persona.reservation_price *= 0.95
        else:
            # Easier for earner: reservation moves UP (more room)
            persona.reservation_price *= 1.10

    # Apply slider overrides from the opponent tuner (values 0-100, default 50)
    opponent_params = scenario.get("opponent_params")
    if opponent_params and isinstance(opponent_params, dict):
        # Aggressiveness → negotiation style shift
        aggr = opponent_params.get("aggressiveness", 50)
        if aggr > 70:
            persona.style = NegotiationStyle.COMPETITIVE
        elif aggr < 30:
            persona.style = NegotiationStyle.ACCOMMODATING

        # Flexibility → widens or tightens reservation price
        flex = opponent_params.get("flexibility", 50)
        flex_factor = 1.0 + (flex - 50) / 200  # 0→0.75, 50→1.0, 100→1.25
        if user_wants_down:
            persona.reservation_price *= flex_factor
        else:
            persona.reservation_price *= flex_factor

        # Patience → direct mapping (0-100 → 0.0-1.0)
        pat = opponent_params.get("patience", 50)
        persona.patience = max(0.05, min(0.95, pat / 100))

        # Market knowledge → transparency proxy
        knowledge = opponent_params.get("knowledge", 50)
        persona.transparency = max(0.05, min(0.95, knowledge / 100))

        # Emotional reactivity → direct mapping
        emotion = opponent_params.get("emotion", 50)
        persona.emotional_reactivity = max(0.05, min(0.95, emotion / 100))

        # Budget authority → pressure level
        budget = opponent_params.get("budget", 50)
        if budget > 70:
            persona.pressure = PressureLevel.LOW
        elif budget < 30:
            persona.pressure = PressureLevel.HIGH

    return persona
