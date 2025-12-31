from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Tier = Literal["beginner", "intermediate", "advanced"]
CardType = Literal["A", "B", "C", "D", "W"]


TIER_ALIASES: dict[str, Tier] = {
    "beginner": "beginner",
    "beg": "beginner",
    "b": "beginner",
    "초보": "beginner",
    "intermediate": "intermediate",
    "inter": "intermediate",
    "i": "intermediate",
    "중수": "intermediate",
    "advanced": "advanced",
    "adv": "advanced",
    "a": "advanced",
    "고수": "advanced",
}


@dataclass(frozen=True)
class CardDef:
    code: str
    card_type: CardType
    stars: int
    name: str


CARDS: dict[str, CardDef] = {
    # A. Base (14)
    "A01": CardDef("A01", "A", 1, "7km+ (tier-scaled)"),
    "A02": CardDef("A02", "A", 2, "8km+ (tier-scaled)"),
    "A03": CardDef("A03", "A", 2, "10km+ (tier-scaled)"),
    "A04": CardDef("A04", "A", 1, "40min+ (tier-scaled)"),
    "A05": CardDef("A05", "A", 2, "60min+ (tier-scaled)"),
    "A06": CardDef("A06", "A", 1, "Warm-up 10min"),
    "A07": CardDef("A07", "A", 1, "Cool-down stretch 10min"),
    "A08": CardDef("A08", "A", 1, "Foam roll / massage 20min"),
    "A09": CardDef("A09", "A", 2, "Strength 10min"),
    "A10": CardDef("A10", "A", 2, "5km with first-time runner"),
    "A11": CardDef("A11", "A", 2, "New route (tier-scaled)"),
    "A12": CardDef("A12", "A", 2, "Build-up (tier-scaled)"),
    "A13": CardDef("A13", "A", 2, "Running drills 5min (with base run)"),
    "A14": CardDef("A14", "A", 1, "Instagram share"),
    # B. Condition (10)
    "B01": CardDef("B01", "B", 1, "Night (>=22:00)"),
    "B02": CardDef("B02", "B", 2, "Dawn (<06:00)"),
    "B03": CardDef("B03", "B", 2, "Below 0°C"),
    "B04": CardDef("B04", "B", 2, "Rain/Snow"),
    "B05": CardDef("B05", "B", 1, "Weekend"),
    "B06": CardDef("B06", "B", 2, "Cold/windy (feels<=-5 or wind>=6)"),
    "B07": CardDef("B07", "B", 2, "Hills (gain>=100 or repeats>=3)"),
    "B08": CardDef("B08", "B", 1, "Track"),
    "B09": CardDef("B09", "B", 1, "Treadmill"),
    "B10": CardDef("B10", "B", 1, "Reflective/light gear"),
    # C. Co-op / Balance (9)
    "C01": CardDef("C01", "C", 1, "Join group run"),
    "C02": CardDef("C02", "C", 2, "Host group run (>=2)"),
    "C03": CardDef("C03", "C", 1, "Pair run (>=2, 20min+)"),
    "C04": CardDef("C04", "C", 2, "Same day 3+ runners"),
    "C05": CardDef("C05", "C", 1, "Thursday meeting"),
    "C06": CardDef("C06", "C", 2, "Pace-making 30min+"),
    "C07": CardDef("C07", "C", 2, "Mixed-tier run"),
    "C08": CardDef("C08", "C", 1, "Easy chat run 60min+"),
    "C09": CardDef("C09", "C", 1, "After-run coffee/stretch"),
    # D. Marathon (5)
    "D01": CardDef("D01", "D", 3, "5-day streak"),
    "D02": CardDef("D02", "D", 3, "Final week 6 runs"),
    "D03": CardDef("D03", "D", 3, "Tier distance goal"),
    "D04": CardDef("D04", "D", 3, "3-day streak"),
    "D05": CardDef("D05", "D", 3, "Alternating days (run-rest-run-rest)"),
    # W. Wild (4)
    "W01": CardDef("W01", "W", 3, "Thu meeting x3"),
    "W02": CardDef("W02", "W", 3, "Host 2x (>=3 ppl each)"),
    "W03": CardDef("W03", "W", 3, "Pace-maker x3"),
    "W04": CardDef("W04", "W", 3, "6 runs in a week"),
}


CARDS_BY_TYPE: dict[CardType, list[str]] = {"A": [], "B": [], "C": [], "D": [], "W": []}
for _code, _card in CARDS.items():
    CARDS_BY_TYPE[_card.card_type].append(_code)
for _t in CARDS_BY_TYPE:
    CARDS_BY_TYPE[_t].sort()
