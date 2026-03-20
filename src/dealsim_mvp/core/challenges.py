"""
Daily Challenge system for DealSim.

Provides 30 micro-negotiation challenges (one month's rotation), each designed
to drill a single negotiation skill in a 3-minute, 3-exchange format.

Scoring dimensions map to the six dimensions in scorer.py:
  Opening Strategy, Information Gathering, Concession Pattern,
  BATNA Usage, Emotional Control, Value Creation.

Each challenge focuses on ONE dimension so feedback is crisp and actionable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from dealsim_mvp.core.persona import (
    NegotiationPersona,
    NegotiationStyle,
    PressureLevel,
)


@dataclass
class DailyChallenge:
    """A compact micro-negotiation scenario."""
    day: int                   # 1-30
    title: str
    category: str              # e.g. "Anchoring", "Information Extraction"
    scoring_focus: str         # maps to a scorer dimension name
    setup: str                 # 1-paragraph scenario the user reads
    max_exchanges: int         # always 3 for daily challenges
    opponent: NegotiationPersona
    success_hint: str          # shown after completion


# ---------------------------------------------------------------------------
# The 30-challenge library
# ---------------------------------------------------------------------------

_CHALLENGES: list[DailyChallenge] = [
    # -----------------------------------------------------------------------
    # Days 1-5: Anchoring
    # -----------------------------------------------------------------------
    DailyChallenge(
        day=1,
        title="The First Number Wins",
        category="Anchoring",
        scoring_focus="Opening Strategy",
        setup=(
            "You are selling a used MacBook Pro to a buyer you met online. "
            "It is in excellent condition and retails new for $2,499. You want at least $1,600. "
            "The buyer is about to ask your price. Anchor high and justify it."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Casey", role="Online buyer",
            style=NegotiationStyle.COMPETITIVE, pressure=PressureLevel.MEDIUM,
            target_price=1200, reservation_price=1700, opening_offer=1000,
            patience=0.4, transparency=0.3, emotional_reactivity=0.5,
            hidden_constraints=["Needs a laptop by Friday for a new job"],
            system_prompt="You want this MacBook cheap. Open at $1,000. Max $1,700.",
        ),
        success_hint="Strong anchors are 15-25% above your target, backed by one concrete justification.",
    ),
    DailyChallenge(
        day=2,
        title="Anchor Against the Expert",
        category="Anchoring",
        scoring_focus="Opening Strategy",
        setup=(
            "You are a freelance designer quoting a logo project to a marketing agency. "
            "Your minimum is $3,000. The agency works with freelancers regularly and knows "
            "market rates. Name your price before they do."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Victor", role="Agency Creative Director",
            style=NegotiationStyle.COMPETITIVE, pressure=PressureLevel.LOW,
            target_price=2000, reservation_price=4000, opening_offer=1800,
            patience=0.7, transparency=0.2, emotional_reactivity=0.2,
            hidden_constraints=["Client already approved a $5K design budget"],
            system_prompt="You are a savvy buyer. Push back on high anchors with market data.",
        ),
        success_hint="Against experts, anchor with specificity: '$4,200 based on 3 concepts + 2 revision rounds' beats a round number.",
    ),
    DailyChallenge(
        day=3,
        title="Re-Anchor After a Low Offer",
        category="Anchoring",
        scoring_focus="Opening Strategy",
        setup=(
            "You are selling your car. A buyer just opened with $8,000 — far below your "
            "target of $14,000. The car's KBB value is $13,500. You need to reset the frame "
            "without insulting the buyer."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Dale", role="Private car buyer",
            style=NegotiationStyle.COMPETITIVE, pressure=PressureLevel.MEDIUM,
            target_price=10000, reservation_price=13000, opening_offer=8000,
            patience=0.5, transparency=0.3, emotional_reactivity=0.6,
            hidden_constraints=["His current car just failed inspection — needs one this week"],
            system_prompt="You opened low at $8,000. You can go up to $13,000 if justified.",
        ),
        success_hint="Acknowledge their offer, then re-anchor with evidence: 'I appreciate the offer. Based on KBB and condition, I'm at $15,000.'",
    ),
    DailyChallenge(
        day=4,
        title="The Salary Anchor",
        category="Anchoring",
        scoring_focus="Opening Strategy",
        setup=(
            "A recruiter just asked 'What are your salary expectations?' for a senior role. "
            "Market range is $130K-$160K. You want $150K. This is your chance to set the frame "
            "for the entire compensation discussion."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Priya", role="Technical Recruiter",
            style=NegotiationStyle.COMPROMISING, pressure=PressureLevel.MEDIUM,
            target_price=125000, reservation_price=155000, opening_offer=120000,
            patience=0.6, transparency=0.3, emotional_reactivity=0.2,
            hidden_constraints=["Hiring manager approved up to $160K for the right candidate"],
            system_prompt="You are a recruiter. Budget is $125K-$155K. Push back on high anchors gently.",
        ),
        success_hint="Anchor with a range where your target is the bottom: 'Based on my experience and market data, I'm targeting $150K-$170K.'",
    ),
    DailyChallenge(
        day=5,
        title="Anchor on Non-Price Terms",
        category="Anchoring",
        scoring_focus="Opening Strategy",
        setup=(
            "You are negotiating a consulting engagement. The daily rate is already agreed at "
            "$1,500. Now you need to anchor on scope: you want a maximum of 20 deliverable pages, "
            "but the client will push for 40+. Set expectations before they state theirs."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Diane", role="VP of Strategy",
            style=NegotiationStyle.COMPETITIVE, pressure=PressureLevel.MEDIUM,
            target_price=45, reservation_price=25, opening_offer=50,
            patience=0.5, transparency=0.2, emotional_reactivity=0.3,
            hidden_constraints=["Board only reads the executive summary anyway — pages don't matter"],
            system_prompt="You want a 50-page report. Can accept 25 pages if quality is high.",
        ),
        success_hint="Anchoring works on any dimension — scope, timeline, deliverables. State your number first with a rationale.",
    ),

    # -----------------------------------------------------------------------
    # Days 6-10: Information Extraction
    # -----------------------------------------------------------------------
    DailyChallenge(
        day=6,
        title="What's Your Budget?",
        category="Information Extraction",
        scoring_focus="Information Gathering",
        setup=(
            "A potential client wants a website redesign. Before you quote, you need to "
            "understand their budget, timeline, and decision process. They have not volunteered "
            "any of this. Extract at least two key constraints in 3 exchanges."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Sam", role="Small business owner",
            style=NegotiationStyle.AVOIDING, pressure=PressureLevel.HIGH,
            target_price=3000, reservation_price=8000, opening_offer=2500,
            patience=0.5, transparency=0.2, emotional_reactivity=0.5,
            hidden_constraints=[
                "Budget is actually $8K but wants to see if you'll go lower",
                "Needs site live before trade show in 6 weeks",
            ],
            system_prompt="Don't reveal your budget or deadline unless directly asked good questions.",
        ),
        success_hint="Open-ended questions ('What does success look like?') extract more than closed ones ('Is your budget $5K?').",
    ),
    DailyChallenge(
        day=7,
        title="The Hidden Deadline",
        category="Information Extraction",
        scoring_focus="Information Gathering",
        setup=(
            "You are negotiating a vendor contract renewal. The vendor seems oddly flexible today. "
            "Something has changed — maybe they are under pressure. Your job: figure out what is "
            "driving their urgency before making any concessions."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Greg", role="Sales rep at your current vendor",
            style=NegotiationStyle.ACCOMMODATING, pressure=PressureLevel.HIGH,
            target_price=50000, reservation_price=38000, opening_offer=52000,
            patience=0.3, transparency=0.3, emotional_reactivity=0.6,
            hidden_constraints=["Quarter ends Friday — needs to close for commission"],
            system_prompt="You need this deal closed by Friday. Don't admit it unless asked directly.",
        ),
        success_hint="When someone is suddenly flexible, ask 'Is there a timing factor I should know about?' — it often unlocks their real constraint.",
    ),
    DailyChallenge(
        day=8,
        title="Reading Between the Lines",
        category="Information Extraction",
        scoring_focus="Information Gathering",
        setup=(
            "Your landlord's property manager just said 'We need to discuss your renewal.' "
            "This could mean a rent increase, a lease change, or they want you to leave. "
            "Before reacting, extract their actual position."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Derek", role="Property manager",
            style=NegotiationStyle.COMPROMISING, pressure=PressureLevel.MEDIUM,
            target_price=1800, reservation_price=1650, opening_offer=1800,
            patience=0.7, transparency=0.3, emotional_reactivity=0.2,
            hidden_constraints=["Building has 15% vacancy — they want to keep you"],
            system_prompt="Propose an 8% increase. Don't reveal the vacancy problem.",
        ),
        success_hint="Start with 'Can you tell me more about what's driving this?' before responding to any number.",
    ),
    DailyChallenge(
        day=9,
        title="The Evasive Client",
        category="Information Extraction",
        scoring_focus="Information Gathering",
        setup=(
            "You are a consultant. A prospect says they want 'something like what you did for "
            "Company X' but won't specify requirements, budget, or timeline. You need at least "
            "one concrete data point before this call ends."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Claire", role="Director of Operations",
            style=NegotiationStyle.AVOIDING, pressure=PressureLevel.MEDIUM,
            target_price=15000, reservation_price=30000, opening_offer=10000,
            patience=0.8, transparency=0.1, emotional_reactivity=0.3,
            hidden_constraints=["Her boss already approved $30K — she's testing your price"],
            system_prompt="Be vague. Only reveal budget info if asked a very specific question.",
        ),
        success_hint="Try bracketing: 'Projects like this typically range $20K-$40K depending on scope. Where does that land for you?'",
    ),
    DailyChallenge(
        day=10,
        title="Probing the Hospital Bill",
        category="Information Extraction",
        scoring_focus="Information Gathering",
        setup=(
            "You received a $4,200 hospital bill. Before negotiating the amount, you need to "
            "understand: what discount programs exist, what authority the rep has, and whether "
            "a payment plan changes the total. Extract this information."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Karen", role="Billing representative",
            style=NegotiationStyle.AVOIDING, pressure=PressureLevel.LOW,
            target_price=4200, reservation_price=3150, opening_offer=4200,
            patience=0.9, transparency=0.1, emotional_reactivity=0.2,
            hidden_constraints=[
                "Prompt-pay discount of 25% is available but not offered proactively",
                "Financial assistance application can reduce by up to 50%",
            ],
            system_prompt="Only mention discounts if the patient asks directly. Be polite but don't volunteer info.",
        ),
        success_hint="Ask: 'Do you offer any prompt-pay discounts or financial assistance programs?' — hospitals almost always do but rarely volunteer them.",
    ),

    # -----------------------------------------------------------------------
    # Days 11-15: BATNA Usage
    # -----------------------------------------------------------------------
    DailyChallenge(
        day=11,
        title="I Have Another Offer",
        category="BATNA Usage",
        scoring_focus="BATNA Usage",
        setup=(
            "You are negotiating salary for a job offer at $120K. You have a competing offer "
            "at $115K from another company. Use this leverage to improve the offer without "
            "coming across as threatening."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Priya", role="Hiring Manager",
            style=NegotiationStyle.COMPROMISING, pressure=PressureLevel.MEDIUM,
            target_price=120000, reservation_price=138000, opening_offer=120000,
            patience=0.5, transparency=0.3, emotional_reactivity=0.3,
            hidden_constraints=["Took 3 months to find this candidate — losing them costs more"],
            system_prompt="Offer is $120K. Budget goes to $138K. Respond seriously to competing offers.",
        ),
        success_hint="State alternatives factually, not as threats: 'I'm weighing another opportunity at $X — I'd prefer to join your team if we can close the gap.'",
    ),
    DailyChallenge(
        day=12,
        title="The Walk-Away Bluff",
        category="BATNA Usage",
        scoring_focus="BATNA Usage",
        setup=(
            "You are buying a used couch on Marketplace for your new apartment. The seller "
            "wants $800. You found a similar one listed at $600 elsewhere. Signal your "
            "alternative without being aggressive."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Alex", role="Private seller",
            style=NegotiationStyle.COMPETITIVE, pressure=PressureLevel.MEDIUM,
            target_price=750, reservation_price=550, opening_offer=800,
            patience=0.4, transparency=0.4, emotional_reactivity=0.6,
            hidden_constraints=["Moving out next week — needs it gone"],
            system_prompt="Selling for $800. Will accept $550 if buyer seems ready to walk.",
        ),
        success_hint="Mention alternatives casually: 'I saw a similar one on the east side for $600. I'd prefer yours if we can work something out.'",
    ),
    DailyChallenge(
        day=13,
        title="BATNA When You Have None",
        category="BATNA Usage",
        scoring_focus="BATNA Usage",
        setup=(
            "Your lease is up next month and you need to renew. Realistically, you cannot move "
            "right now. Your landlord proposed a 10% increase. You have a weak BATNA — but you "
            "don't have to reveal that. Create leverage from nothing."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Patricia", role="Landlord",
            style=NegotiationStyle.COMPETITIVE, pressure=PressureLevel.LOW,
            target_price=1650, reservation_price=1550, opening_offer=1650,
            patience=0.8, transparency=0.3, emotional_reactivity=0.5,
            hidden_constraints=["Unit needs $3K in repairs she hasn't done — dreads turnover"],
            system_prompt="Proposing 10% increase. Will settle for 3% to avoid turnover costs.",
        ),
        success_hint="Even without a real alternative, 'I've been looking at places in [neighborhood]' introduces doubt. Landlords fear vacancy more than they value marginal rent.",
    ),
    DailyChallenge(
        day=14,
        title="Strengthen Their Weak BATNA",
        category="BATNA Usage",
        scoring_focus="BATNA Usage",
        setup=(
            "You are a freelance developer. Your client is threatening to hire someone cheaper. "
            "You know their codebase is complex and onboarding a new developer would take months. "
            "Make them realize their BATNA is weaker than they think."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Jordan", role="Startup CTO",
            style=NegotiationStyle.COMPETITIVE, pressure=PressureLevel.HIGH,
            target_price=80, reservation_price=130, opening_offer=75,
            patience=0.3, transparency=0.2, emotional_reactivity=0.6,
            hidden_constraints=["Last developer took 6 weeks to onboard — can't afford that again"],
            system_prompt="Threaten to hire someone cheaper. Fold if they point out switching costs.",
        ),
        success_hint="Reframe their BATNA: 'You could hire someone at $75/hr, but factoring in 6 weeks of onboarding, you'd spend more than the rate difference.'",
    ),
    DailyChallenge(
        day=15,
        title="The Vendor Lock-In Escape",
        category="BATNA Usage",
        scoring_focus="BATNA Usage",
        setup=(
            "Your SaaS vendor is raising prices 25%. You are somewhat locked in due to data "
            "migration costs, but you have evaluated two competitors. Use your research to "
            "negotiate the increase down."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Nina", role="Account Manager",
            style=NegotiationStyle.COMPETITIVE, pressure=PressureLevel.MEDIUM,
            target_price=60000, reservation_price=50000, opening_offer=62500,
            patience=0.6, transparency=0.2, emotional_reactivity=0.2,
            hidden_constraints=["Churn rate is high this quarter — retention is priority"],
            system_prompt="Price increase is 25%. Can go down to 0% increase to retain. Be firm initially.",
        ),
        success_hint="Naming specific competitors with pricing signals you've done homework: 'Competitor X quoted us $45K with migration support included.'",
    ),

    # -----------------------------------------------------------------------
    # Days 16-20: Concession Management
    # -----------------------------------------------------------------------
    DailyChallenge(
        day=16,
        title="The Shrinking Concession",
        category="Concession Management",
        scoring_focus="Concession Pattern",
        setup=(
            "You are selling a service package at $10,000. The buyer wants $7,000. You can go "
            "as low as $8,500. Make three concessions that get progressively smaller, signaling "
            "you are approaching your floor."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Mark", role="Procurement Manager",
            style=NegotiationStyle.COMPETITIVE, pressure=PressureLevel.MEDIUM,
            target_price=7000, reservation_price=9000, opening_offer=7000,
            patience=0.5, transparency=0.3, emotional_reactivity=0.3,
            hidden_constraints=["Budget is actually $9,000 — testing your floor"],
            system_prompt="You want $7,000. Can pay up to $9,000. Test their concession pattern.",
        ),
        success_hint="Concessions should shrink: $500 then $250 then $100. This signals you're near your limit and discourages further pushing.",
    ),
    DailyChallenge(
        day=17,
        title="Never Concede for Free",
        category="Concession Management",
        scoring_focus="Concession Pattern",
        setup=(
            "You are a contractor and the homeowner wants a $2,000 discount on a $15,000 "
            "kitchen remodel. Before giving any discount, extract a concession from them: "
            "faster payment terms, a referral commitment, or scope reduction."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Linda", role="Homeowner",
            style=NegotiationStyle.COMPETITIVE, pressure=PressureLevel.MEDIUM,
            target_price=13000, reservation_price=14500, opening_offer=12500,
            patience=0.5, transparency=0.4, emotional_reactivity=0.5,
            hidden_constraints=["Will happily pay deposit upfront and refer friends"],
            system_prompt="You want a $2K discount. Will trade referrals or fast payment if asked.",
        ),
        success_hint="Every concession should be conditional: 'I can do $14,000 if we go with the standard countertops instead of quartz.'",
    ),
    DailyChallenge(
        day=18,
        title="The Split-the-Difference Trap",
        category="Concession Management",
        scoring_focus="Concession Pattern",
        setup=(
            "You quoted a project at $20,000. The client offered $14,000. They now say 'Let's "
            "just split the difference at $17,000.' This feels fair but favors them (your floor "
            "is $18,000). Avoid the trap without killing the deal."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Tom", role="Operations Director",
            style=NegotiationStyle.COMPROMISING, pressure=PressureLevel.MEDIUM,
            target_price=17000, reservation_price=19000, opening_offer=14000,
            patience=0.5, transparency=0.3, emotional_reactivity=0.4,
            hidden_constraints=["Budget is $19K — the 'split' was a negotiation tactic"],
            system_prompt="Propose splitting the difference at $17K. Accept $18K-$19K if pushed.",
        ),
        success_hint="Counter 'split the difference' with: 'I appreciate the fairness instinct. My numbers show $19K is the floor for this scope. If we split from there, that's $18,500.'",
    ),
    DailyChallenge(
        day=19,
        title="Trading, Not Giving",
        category="Concession Management",
        scoring_focus="Concession Pattern",
        setup=(
            "You are renewing an annual SaaS subscription. The vendor wants $24,000/year (20% "
            "increase). You want to stay at $20,000. You have non-monetary items to trade: "
            "case study participation, a 2-year commitment, or an intro to your network."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Nina", role="Account manager",
            style=NegotiationStyle.COLLABORATIVE, pressure=PressureLevel.MEDIUM,
            target_price=24000, reservation_price=20000, opening_offer=24000,
            patience=0.6, transparency=0.4, emotional_reactivity=0.2,
            hidden_constraints=["A case study from this customer is worth $3K in marketing value"],
            system_prompt="Renewal at $24K. Will trade down for case study or multi-year commit.",
        ),
        success_hint="Package your concession: 'I'll commit to 2 years and participate in a case study if we hold at $20K.'",
    ),
    DailyChallenge(
        day=20,
        title="Conceding on the Right Dimension",
        category="Concession Management",
        scoring_focus="Concession Pattern",
        setup=(
            "You are hiring a contractor at $100/hr. They want $125/hr. You cannot pay more "
            "than $110/hr, but you can offer guaranteed minimum hours (20 hrs/week), faster "
            "payment (net-7 instead of net-30), or a longer contract."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Raj", role="Independent contractor",
            style=NegotiationStyle.COLLABORATIVE, pressure=PressureLevel.MEDIUM,
            target_price=125, reservation_price=105, opening_offer=130,
            patience=0.5, transparency=0.5, emotional_reactivity=0.3,
            hidden_constraints=["Values guaranteed hours more than a higher rate"],
            system_prompt="You want $125/hr. Would accept $105/hr with guaranteed 20 hrs/week.",
        ),
        success_hint="Find the concession that costs you little but matters to them. Guaranteed hours might cost the same but feel like a raise.",
    ),

    # -----------------------------------------------------------------------
    # Days 21-25: Emotional Pressure Handling
    # -----------------------------------------------------------------------
    DailyChallenge(
        day=21,
        title="The Exploding Offer",
        category="Emotional Pressure",
        scoring_focus="Emotional Control",
        setup=(
            "A car dealer says: 'This price is only good until we close tonight. If you walk "
            "out, I can't guarantee it tomorrow.' You like the car but haven't finished "
            "researching. Handle the pressure without caving or burning the bridge."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Tony", role="Car salesperson",
            style=NegotiationStyle.COMPETITIVE, pressure=PressureLevel.HIGH,
            target_price=27000, reservation_price=24000, opening_offer=28000,
            patience=0.2, transparency=0.1, emotional_reactivity=0.5,
            hidden_constraints=["The price will still be available tomorrow — it's a pressure tactic"],
            system_prompt="Create urgency. 'Offer expires tonight.' Back down if they call the bluff.",
        ),
        success_hint="'I appreciate the urgency. Let me step out for 15 minutes to review my numbers. If the offer is as good as you say, it'll still make sense when I get back.'",
    ),
    DailyChallenge(
        day=22,
        title="The Guilt Trip",
        category="Emotional Pressure",
        scoring_focus="Emotional Control",
        setup=(
            "A client you've worked with for years asks for a 40% discount on your rate, "
            "saying: 'After everything we've been through together, I thought you'd help me "
            "out here.' Maintain the relationship without capitulating on price."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Paula", role="Long-time client",
            style=NegotiationStyle.ACCOMMODATING, pressure=PressureLevel.HIGH,
            target_price=60, reservation_price=90, opening_offer=55,
            patience=0.4, transparency=0.5, emotional_reactivity=0.8,
            hidden_constraints=["Company is doing fine financially — this is a negotiation tactic"],
            system_prompt="Use the relationship as leverage. Say things like 'I thought we were friends' and 'After all these years.' Accept near full rate if they hold firm warmly.",
        ),
        success_hint="Validate the relationship, separate it from pricing: 'I value our partnership — that's why I want to be transparent about my costs rather than cut quality.'",
    ),
    DailyChallenge(
        day=23,
        title="The Angry Buyer",
        category="Emotional Pressure",
        scoring_focus="Emotional Control",
        setup=(
            "You quoted a client $8,000 for a project. They respond angrily: 'Are you kidding? "
            "Your competitor quoted half that. I thought you were serious about working with us.' "
            "Stay composed and hold your ground."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Steve", role="VP of Engineering",
            style=NegotiationStyle.COMPETITIVE, pressure=PressureLevel.MEDIUM,
            target_price=4000, reservation_price=7500, opening_offer=3500,
            patience=0.3, transparency=0.1, emotional_reactivity=0.8,
            hidden_constraints=["The 'competitor quote' is fabricated — no one quoted that low"],
            system_prompt="Act frustrated and slightly angry. Claim a competitor quoted $4K. De-escalate if they stay calm and ask good questions.",
        ),
        success_hint="Name the emotion without matching it: 'I can see this wasn't the number you expected. Help me understand what scope the competitor quoted for $4K.'",
    ),
    DailyChallenge(
        day=24,
        title="The Silent Treatment",
        category="Emotional Pressure",
        scoring_focus="Emotional Control",
        setup=(
            "You just named your salary expectation of $140K. The hiring manager paused and "
            "has been silent for an uncomfortable 10 seconds. The silence is designed to make "
            "you backtrack. Do not fill it with a concession."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="James", role="Hiring Manager",
            style=NegotiationStyle.COMPETITIVE, pressure=PressureLevel.LOW,
            target_price=120000, reservation_price=145000, opening_offer=115000,
            patience=0.9, transparency=0.1, emotional_reactivity=0.1,
            hidden_constraints=["Budget goes to $145K — the silence is a tactic"],
            system_prompt="Use silence after they name a number. If they don't concede, eventually counter at $125K.",
        ),
        success_hint="After you state your number, stop talking. If they stay silent, you can say 'Take your time — I'm happy to discuss the rationale' without lowering your ask.",
    ),
    DailyChallenge(
        day=25,
        title="Good Cop, Bad Cop",
        category="Emotional Pressure",
        scoring_focus="Emotional Control",
        setup=(
            "You are negotiating a contract with a company. The friendly account manager loves "
            "your proposal, but her boss (on the call) keeps raising objections and saying the "
            "price is too high. Recognize the tactic and negotiate with both."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Rachel & Mr. Burke", role="Account Manager and VP",
            style=NegotiationStyle.COMPETITIVE, pressure=PressureLevel.MEDIUM,
            target_price=40000, reservation_price=55000, opening_offer=35000,
            patience=0.5, transparency=0.2, emotional_reactivity=0.4,
            hidden_constraints=["Both already agreed to your price internally — this is a negotiation play"],
            system_prompt="Play good-cop/bad-cop. Rachel is friendly, Burke is harsh. Both want the deal at $50K.",
        ),
        success_hint="Address both: 'Rachel, I appreciate your support. Mr. Burke, I'd love to address your concerns directly — what specific ROI data would help?'",
    ),

    # -----------------------------------------------------------------------
    # Days 26-30: Multi-Issue Trades
    # -----------------------------------------------------------------------
    DailyChallenge(
        day=26,
        title="Expand the Pie",
        category="Multi-Issue Trades",
        scoring_focus="Value Creation",
        setup=(
            "You are negotiating a job offer stuck at $130K (you want $145K). They cannot "
            "budge on base salary. Find other dimensions — signing bonus, equity, remote days, "
            "PTO, title — to close the $15K gap in perceived value."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Sarah", role="HR Director",
            style=NegotiationStyle.COLLABORATIVE, pressure=PressureLevel.MEDIUM,
            target_price=130000, reservation_price=132000, opening_offer=130000,
            patience=0.6, transparency=0.4, emotional_reactivity=0.2,
            hidden_constraints=[
                "Can offer $10K signing bonus from a different budget",
                "Extra PTO days are essentially free to approve",
                "Remote days are pre-approved company-wide",
            ],
            system_prompt="Base is locked at $130-$132K. Be generous on signing bonus, PTO, and remote.",
        ),
        success_hint="When base is stuck, pivot: 'If base is firm, could we look at a signing bonus, additional PTO, or an equity refresh to close the gap?'",
    ),
    DailyChallenge(
        day=27,
        title="The Package Deal",
        category="Multi-Issue Trades",
        scoring_focus="Value Creation",
        setup=(
            "You are a vendor selling both software licenses ($50K) and training services ($15K). "
            "The client only wants the software. Bundle training in at a discount to increase "
            "the total deal size and create value for both sides."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Carol", role="IT Director",
            style=NegotiationStyle.COMPROMISING, pressure=PressureLevel.MEDIUM,
            target_price=45000, reservation_price=55000, opening_offer=42000,
            patience=0.5, transparency=0.4, emotional_reactivity=0.3,
            hidden_constraints=["Training budget is separate and unspent — could easily add it"],
            system_prompt="You want the software for $42-$45K. Training sounds useful if it doesn't add much.",
        ),
        success_hint="Bundle creates win-win: 'For $52K I can include the full training package (normally $15K). Your team gets certified and you save $13K versus buying separately.'",
    ),
    DailyChallenge(
        day=28,
        title="Trade Across Time",
        category="Multi-Issue Trades",
        scoring_focus="Value Creation",
        setup=(
            "Your freelance client wants to cut your rate by 20% for the next project. "
            "Instead of a flat rate cut, propose a structure that works for both: lower rate "
            "now in exchange for guaranteed future work, royalties, or equity."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Mike", role="Startup CEO",
            style=NegotiationStyle.COMPETITIVE, pressure=PressureLevel.HIGH,
            target_price=80, reservation_price=110, opening_offer=75,
            patience=0.3, transparency=0.3, emotional_reactivity=0.5,
            hidden_constraints=["Has 6 months of projects lined up — guaranteed volume is real"],
            system_prompt="You want a rate cut. Will offer guaranteed hours or future projects if they propose it.",
        ),
        success_hint="Trade present value for future value: 'I'll do $90/hr (10% discount) for this project if we lock in 3 months of work at that rate.'",
    ),
    DailyChallenge(
        day=29,
        title="The Rent Renewal Package",
        category="Multi-Issue Trades",
        scoring_focus="Value Creation",
        setup=(
            "Your landlord wants an 8% rent increase. You want to stay flat. Instead of just "
            "arguing about the number, propose a multi-term deal: lease length, maintenance "
            "responsibilities, improvement allowances, or payment terms."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Patricia", role="Landlord",
            style=NegotiationStyle.COMPROMISING, pressure=PressureLevel.MEDIUM,
            target_price=1620, reservation_price=1520, opening_offer=1620,
            patience=0.6, transparency=0.4, emotional_reactivity=0.5,
            hidden_constraints=[
                "A 2-year lease at flat rent is more valuable than a 1-year at 8% increase",
                "Tenant doing minor maintenance saves her $2K/year in property management",
            ],
            system_prompt="Proposing 8% increase. Will accept flat rent for a 2-year term or maintenance trade.",
        ),
        success_hint="'I'd like to stay at the current rate. In exchange, I'll sign a 2-year lease and handle minor maintenance myself. That saves you turnover cost and management fees.'",
    ),
    DailyChallenge(
        day=30,
        title="The Final Boss: Multi-Dimensional Close",
        category="Multi-Issue Trades",
        scoring_focus="Value Creation",
        setup=(
            "You have a job offer at $135K, 10 days PTO, no signing bonus, and a 'Senior' "
            "title. You want $150K, 20 days PTO, $15K signing bonus, and a 'Lead' title. "
            "The company values you but has constraints on each dimension. In 3 exchanges, "
            "maximize your total package by trading intelligently across all four dimensions."
        ),
        max_exchanges=3,
        opponent=NegotiationPersona(
            name="Priya & Thomas", role="Recruiter and HR Comp Analyst",
            style=NegotiationStyle.COLLABORATIVE, pressure=PressureLevel.MEDIUM,
            target_price=135000, reservation_price=142000, opening_offer=135000,
            patience=0.5, transparency=0.3, emotional_reactivity=0.2,
            hidden_constraints=[
                "Base can go to $142K max (pay band)",
                "PTO is flexible — 15-20 days costs them nothing",
                "Signing bonus up to $10K from recruitment budget",
                "Title change to 'Lead' requires VP approval but is doable",
            ],
            system_prompt=(
                "Offer is $135K/10 PTO/no bonus/Senior title. "
                "Can move to $142K/20 PTO/$10K bonus/Lead title across dimensions. "
                "Trade willingly on PTO and title, hold firmer on base and bonus."
            ),
        ),
        success_hint="Prioritize what matters most to you, concede what costs them least. 'If base stays at $140K, I'd accept 15 days PTO if we add the Lead title and a $10K signing bonus.'",
    ),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_daily_challenge(day: int | None = None) -> DailyChallenge:
    """
    Return today's 3-minute micro-negotiation challenge.

    Parameters
    ----------
    day:
        Explicit day number (1-30). If None, uses today's date mod 30 + 1
        so the rotation cycles monthly.

    Returns
    -------
    DailyChallenge with a 1-paragraph scenario, pre-configured opponent,
    max 3 exchanges, and a single scoring focus dimension.
    """
    if day is None:
        day = (date.today().toordinal() % 30) + 1
    day = max(1, min(30, day))
    return _CHALLENGES[day - 1]


def get_challenge_by_category(category: str) -> list[DailyChallenge]:
    """Return all challenges in a given category."""
    return [c for c in _CHALLENGES if c.category.lower() == category.lower()]


def list_categories() -> list[str]:
    """Return the ordered list of challenge categories."""
    seen: set[str] = set()
    cats: list[str] = []
    for c in _CHALLENGES:
        if c.category not in seen:
            seen.add(c.category)
            cats.append(c.category)
    return cats


def list_all_challenges() -> list[dict]:
    """Return lightweight metadata for all 30 challenges."""
    return [
        {
            "day": c.day,
            "title": c.title,
            "category": c.category,
            "scoring_focus": c.scoring_focus,
        }
        for c in _CHALLENGES
    ]
