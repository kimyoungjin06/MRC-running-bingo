#!/usr/bin/env python3
from __future__ import annotations

import argparse
import dataclasses
import json
import math
import random
import statistics
from dataclasses import dataclass
from typing import Iterable, Literal


Tier = Literal["beginner", "intermediate", "advanced"]


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

TIER_ORDER: dict[Tier, int] = {"beginner": 0, "intermediate": 1, "advanced": 2}


@dataclass(frozen=True)
class CardDef:
    code: str
    card_type: Literal["A", "B", "C", "D", "W"]
    stars: int
    name: str


CARDS: dict[str, CardDef] = {
    # A. Base
    "A01": CardDef("A01", "A", 1, "7km+"),
    "A02": CardDef("A02", "A", 2, "8km+"),
    "A03": CardDef("A03", "A", 2, "10km+"),
    "A04": CardDef("A04", "A", 1, "40min+"),
    "A05": CardDef("A05", "A", 2, "60min+"),
    "A06": CardDef("A06", "A", 1, "Warm-up 10min"),
    "A07": CardDef("A07", "A", 1, "Cool-down stretch 10min"),
    "A08": CardDef("A08", "A", 1, "Foam roll / massage 20min"),
    "A09": CardDef("A09", "A", 2, "Strength 10min"),
    "A10": CardDef("A10", "A", 2, "5km with first-time runner"),
    "A11": CardDef("A11", "A", 2, "New route"),
    "A12": CardDef("A12", "A", 2, "Build-up / negative split"),
    "A13": CardDef("A13", "A", 2, "Running drills 5min (base run)"),
    "A14": CardDef("A14", "A", 1, "Instagram share"),
    # B. Condition
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
    # C. Co-op
    "C01": CardDef("C01", "C", 1, "Join group run"),
    "C02": CardDef("C02", "C", 2, "Host group run (>=2)"),
    "C03": CardDef("C03", "C", 1, "Pair run (>=2, 20min+)"),
    "C04": CardDef("C04", "C", 2, "Same day 3+ runners"),
    "C05": CardDef("C05", "C", 1, "Thursday meeting"),
    "C06": CardDef("C06", "C", 2, "Pace-making 30min+"),
    "C07": CardDef("C07", "C", 2, "Mixed-tier run"),
    "C08": CardDef("C08", "C", 1, "Easy chat run 60min+"),
    "C09": CardDef("C09", "C", 1, "After-run coffee/stretch"),
    # D. Marathon
    "D01": CardDef("D01", "D", 3, "5-day streak"),
    "D02": CardDef("D02", "D", 3, "Final week 6 runs"),
    "D03": CardDef("D03", "D", 3, "Tier distance goal"),
    "D04": CardDef("D04", "D", 3, "3-day streak"),
    "D05": CardDef("D05", "D", 3, "Alternating days"),
    # W. Wild
    "W01": CardDef("W01", "W", 3, "Thu meeting x3"),
    "W02": CardDef("W02", "W", 3, "Host 2x (>=3 ppl each)"),
    "W03": CardDef("W03", "W", 3, "Pace-maker x3"),
    "W04": CardDef("W04", "W", 3, "6 runs in a week"),
}


CARDS_BY_TYPE: dict[str, list[str]] = {"A": [], "B": [], "C": [], "D": [], "W": []}
for _code, _card in CARDS.items():
    CARDS_BY_TYPE[_card.card_type].append(_code)
for _t in CARDS_BY_TYPE:
    CARDS_BY_TYPE[_t].sort()


@dataclass
class TierParams:
    p_run: float
    p_two_a_day: float
    pace_mean: float  # min/km
    pace_sd: float
    duration_mean: float  # min
    duration_sd: float


DEFAULT_TIER_PARAMS: dict[Tier, TierParams] = {
    "beginner": TierParams(p_run=0.50, p_two_a_day=0.02, pace_mean=7.2, pace_sd=0.9, duration_mean=35, duration_sd=12),
    "intermediate": TierParams(p_run=0.58, p_two_a_day=0.03, pace_mean=6.2, pace_sd=0.8, duration_mean=45, duration_sd=15),
    "advanced": TierParams(p_run=0.70, p_two_a_day=0.05, pace_mean=5.4, pace_sd=0.7, duration_mean=55, duration_sd=18),
}


@dataclass(frozen=True)
class Weather:
    temperature_c: float
    feels_like_c: float
    wind_m_s: float
    precipitation: Literal["none", "rain", "snow"]


@dataclass(frozen=True)
class RunEvent:
    day_index: int
    week_index: int
    day_of_week: int  # 0=Mon
    start_hour: int
    duration_min: int
    pace_min_per_km: float
    distance_km: float
    weather: Weather
    is_weekend: bool
    is_track: bool
    is_treadmill: bool
    elevation_gain_m: int
    hill_repeats: int
    has_light_gear: bool
    with_new_runner: bool
    did_warmup: bool
    did_cooldown: bool
    did_foam_roll: bool
    did_strength: bool
    did_drills: bool
    did_log: bool
    is_new_route: bool
    is_build_up: bool
    # group context
    day_runners_count: int
    is_group: bool
    group_size: int
    group_tiers: tuple[Tier, ...]
    is_thursday_meeting: bool
    is_bungae: bool
    is_host: bool
    after_social: bool
    is_easy: bool


@dataclass
class PlayerState:
    name: str
    tier: Tier
    board: dict[str, list[str]]  # A/B/C/D/W -> codes
    grid: list[list[str]] = dataclasses.field(default_factory=list)
    bingo_lines: list[list[str]] = dataclasses.field(default_factory=list)
    center_w_code: str | None = None

    completed: set[str] = dataclasses.field(default_factory=set)

    finished_day: int | None = None
    finish_time: float | None = None
    five_bingo_time: float | None = None
    bingo_line_count: int = 0

    has_token: bool = False
    token_earned_once: bool = False
    tokens_earned: int = 0
    tokens_spent_seal: int = 0
    tokens_spent_shield: int = 0
    times_sealed: int = 0
    seal_targets_used: set[str] = dataclasses.field(default_factory=set)
    sealed_type: Literal["B", "C"] | None = None
    sealed_runs_left: int = 0

    total_distance_km: float = 0.0
    weekly_run_counts: list[int] = dataclasses.field(default_factory=lambda: [0, 0, 0, 0])
    final_week_runs: int = 0
    last_day_ran: int | None = None
    consecutive_days: int = 0

    thursday_attendance: int = 0
    hosted_bungae_3plus: int = 0
    pacemaker_count: int = 0

    def completed_count(self) -> int:
        return len(self.completed)

    def completed_star_sum(self) -> int:
        return sum(CARDS[c].stars for c in self.completed)


@dataclass(frozen=True)
class SeasonConfig:
    weeks: int = 4
    thursday_participants_min: int = 5
    thursday_participants_max: int = 8
    final_week_runs_needed: int = 6
    w01_thu_needed: int = 3
    w02_host_needed: int = 2
    w03_pace_needed: int = 3


def clamp_int(value: float, min_value: int, max_value: int) -> int:
    return max(min_value, min(int(round(value)), max_value))


def sample_weather(rng: random.Random) -> Weather:
    temperature = rng.gauss(-2.0, 6.0)
    wind = max(0.0, rng.gammavariate(2.0, 1.5))  # mean ~3
    precip_roll = rng.random()
    if precip_roll < 0.22:
        precipitation: Literal["none", "rain", "snow"] = "snow" if temperature <= 0 else "rain"
    else:
        precipitation = "none"
    feels_like = temperature - (0.7 * wind) - (1.0 if precipitation != "none" else 0.0)
    return Weather(temperature_c=temperature, feels_like_c=feels_like, wind_m_s=wind, precipitation=precipitation)


def sample_start_hour(rng: random.Random, *, is_weekend: bool, is_thursday_meeting: bool, is_group: bool) -> int:
    if is_thursday_meeting:
        return 19
    if is_group and is_weekend:
        return 9
    roll = rng.random()
    if roll < 0.16:
        return rng.choice([5, 5, 5, 6])
    if roll < 0.62:
        return rng.choice([18, 19, 19, 20, 21])
    return rng.choice([7, 8, 12, 13, 14, 15])


def sample_run_metrics(rng: random.Random, tier_params: TierParams, *, is_group: bool, is_easy: bool) -> tuple[int, float, float]:
    pace = max(3.8, rng.gauss(tier_params.pace_mean, tier_params.pace_sd))
    duration = max(18.0, rng.gauss(tier_params.duration_mean, tier_params.duration_sd))
    if is_group:
        duration = max(duration, 30.0)
        pace += 0.35
        if is_easy:
            pace += 0.45
            duration = max(duration, 50.0)
    duration_int = clamp_int(duration, 18, 120)
    distance = max(1.0, duration_int / pace)
    return duration_int, pace, distance


def weighted_sample_without_replacement(
    rng: random.Random, items: list[str], weights: list[float], k: int
) -> list[str]:
    if k <= 0:
        return []
    if k >= len(items):
        return list(items)
    picked: list[str] = []
    pool = list(items)
    w = list(weights)
    for _ in range(k):
        total = sum(w)
        if total <= 0:
            choice = rng.choice(pool)
        else:
            choice = rng.choices(pool, weights=w, k=1)[0]
        idx = pool.index(choice)
        picked.append(choice)
        pool.pop(idx)
        w.pop(idx)
    return picked


def counts_for_tier(tier: Tier, *, variant_w: bool) -> dict[str, int]:
    base = {"A": 10, "B": 7, "C": 5, "D": 2, "W": 1}
    if not variant_w:
        return base
    if tier == "intermediate":
        return {"A": 10, "B": 7, "C": 5, "D": 1, "W": 2}
    if tier == "advanced":
        return {"A": 9, "B": 6, "C": 5, "D": 2, "W": 3}
    return base


def draft_board(
    rng: random.Random,
    tier: Tier,
    *,
    variant_w: bool,
    draft_mode: Literal["weighted", "random", "easiest"],
    alpha: float,
    min_star_sum: int | None = None,
    max_attempts: int = 200,
) -> dict[str, list[str]]:
    counts = counts_for_tier(tier, variant_w=variant_w)
    attempts = 0
    while True:
        attempts += 1
        chosen: set[str] = set()
        board: dict[str, list[str]] = {t: [] for t in ["A", "B", "C", "D", "W"]}

        for card_type, n in counts.items():
            pool = [c for c in CARDS_BY_TYPE[card_type] if c not in chosen]
            if draft_mode == "random":
                pick = rng.sample(pool, n)
            elif draft_mode == "easiest":
                pick = sorted(pool, key=lambda code: (CARDS[code].stars, code))[:n]
            else:
                weights = []
                for code in pool:
                    stars = CARDS[code].stars
                    w = math.exp(-alpha * stars)
                    if tier == "beginner" and code in {"A03", "A05", "D02", "W04"}:
                        w *= 0.55
                    if tier == "intermediate" and code in {"W04"}:
                        w *= 0.80
                    weights.append(w)
                pick = weighted_sample_without_replacement(rng, pool, weights, n)

            chosen.update(pick)
            board[card_type] = sorted(pick)

        if min_star_sum is None:
            return board
        star_sum = sum(CARDS[c].stars for t in board for c in board[t])
        if star_sum >= min_star_sum:
            return board
        if attempts >= max_attempts:
            return board


def tier_value(tier: Tier, beginner: float, intermediate: float, advanced: float) -> float:
    if tier == "beginner":
        return beginner
    if tier == "intermediate":
        return intermediate
    return advanced


def _is_corner(pos: tuple[int, int]) -> bool:
    r, c = pos
    return (r, c) in {(0, 0), (0, 4), (4, 0), (4, 4)}


def _is_adjacent(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1


def build_bingo_lines(grid: list[list[str]]) -> list[list[str]]:
    lines: list[list[str]] = []
    size = 5
    # rows
    for r in range(size):
        lines.append([grid[r][c] for c in range(size)])
    # cols
    for c in range(size):
        lines.append([grid[r][c] for r in range(size)])
    # diagonals
    lines.append([grid[i][i] for i in range(size)])
    lines.append([grid[i][size - 1 - i] for i in range(size)])
    return lines


def count_completed_lines(lines: list[list[str]], completed: set[str]) -> int:
    return sum(1 for line in lines if all(code in completed for code in line))


def place_board(
    rng: random.Random,
    board: dict[str, list[str]],
    *,
    tier: Tier,
    variant_w: bool,
) -> tuple[list[list[str]], str]:
    size = 5
    center = (2, 2)
    corners = [(0, 0), (0, 4), (4, 0), (4, 4)]

    w_codes = list(board["W"])
    if not w_codes:
        raise ValueError("board has no W cards")

    center_w = min(w_codes, key=lambda code: (CARDS[code].stars, code))
    remaining_w = [c for c in w_codes if c != center_w]

    for _attempt in range(400):
        grid: list[list[str]] = [["" for _ in range(size)] for _ in range(size)]
        occupied: set[tuple[int, int]] = set()

        grid[center[0]][center[1]] = center_w
        occupied.add(center)

        if variant_w and tier == "intermediate" and remaining_w:
            pos = rng.choice(corners)
            grid[pos[0]][pos[1]] = remaining_w[0]
            occupied.add(pos)

        if variant_w and tier == "advanced" and len(remaining_w) >= 2:
            diag = rng.choice(["main", "anti"])
            diag_corners = [(0, 0), (4, 4)] if diag == "main" else [(0, 4), (4, 0)]
            for code, pos in zip(sorted(remaining_w)[:2], diag_corners, strict=False):
                grid[pos[0]][pos[1]] = code
                occupied.add(pos)

        empty_positions = [(r, c) for r in range(size) for c in range(size) if (r, c) not in occupied]

        # Place C first (no orthogonal adjacency).
        c_positions: list[tuple[int, int]] = []
        ok = True
        for code in board["C"]:
            candidates = [p for p in empty_positions if all(not _is_adjacent(p, q) for q in c_positions)]
            if not candidates:
                ok = False
                break
            pos = rng.choice(candidates)
            grid[pos[0]][pos[1]] = code
            c_positions.append(pos)
            empty_positions.remove(pos)
        if not ok:
            continue

        # Place D (not in corners).
        d_candidates = [p for p in empty_positions if not _is_corner(p)]
        if len(board["D"]) > len(d_candidates):
            continue
        for code in board["D"]:
            pos = rng.choice(d_candidates)
            grid[pos[0]][pos[1]] = code
            empty_positions.remove(pos)
            d_candidates.remove(pos)

        # Fill remaining with A then B (random order within type).
        rest_codes = list(board["A"]) + list(board["B"])
        rng.shuffle(rest_codes)
        if len(rest_codes) != len(empty_positions):
            continue
        for code, pos in zip(rest_codes, empty_positions, strict=False):
            grid[pos[0]][pos[1]] = code

        if any(grid[r][c] == "" for r in range(size) for c in range(size)):
            continue

        return grid, center_w

    raise RuntimeError("failed to place board with constraints")


def check_card_satisfied(card_code: str, player: PlayerState, run: RunEvent) -> bool:
    c = card_code
    base_distance = tier_value(player.tier, 5.0, 7.0, 10.0)
    base_duration = tier_value(player.tier, 30.0, 40.0, 50.0)
    if c != "A10" and (run.distance_km < base_distance or run.duration_min < base_duration):
        return False
    if c == "A01":
        return run.distance_km >= tier_value(player.tier, 5.0, 7.0, 10.0)
    if c == "A02":
        return run.distance_km >= tier_value(player.tier, 6.0, 8.0, 12.0)
    if c == "A03":
        return run.distance_km >= tier_value(player.tier, 7.0, 10.0, 15.0)
    if c == "A04":
        return run.duration_min >= tier_value(player.tier, 30.0, 40.0, 50.0)
    if c == "A05":
        return run.duration_min >= tier_value(player.tier, 50.0, 60.0, 70.0)
    if c == "A06":
        return run.did_warmup
    if c == "A07":
        return run.did_cooldown
    if c == "A08":
        return run.did_foam_roll
    if c == "A09":
        return run.did_strength
    if c == "A10":
        return run.with_new_runner and run.distance_km >= 5.0
    if c == "A11":
        return run.is_new_route and run.distance_km >= tier_value(player.tier, 5.0, 7.0, 10.0)
    if c == "A12":
        return run.is_build_up and run.duration_min >= tier_value(player.tier, 30.0, 40.0, 50.0)
    if c == "A13":
        return run.did_drills
    if c == "A14":
        return run.did_log

    if c == "B01":
        return run.start_hour >= 22
    if c == "B02":
        return run.start_hour < 6
    if c == "B03":
        return run.weather.temperature_c <= 0.0
    if c == "B04":
        return run.weather.precipitation != "none"
    if c == "B05":
        return run.is_weekend
    if c == "B06":
        return run.weather.feels_like_c <= -5.0 or run.weather.wind_m_s >= 6.0
    if c == "B07":
        return run.elevation_gain_m >= 100 or run.hill_repeats >= 3
    if c == "B08":
        return run.is_track
    if c == "B09":
        return run.is_treadmill
    if c == "B10":
        return run.has_light_gear

    if c == "C01":
        return run.is_group and run.group_size >= 2
    if c == "C02":
        return run.is_bungae and run.is_group and run.is_host and run.group_size >= 2
    if c == "C03":
        return run.is_group and run.group_size >= 2 and run.duration_min >= 20
    if c == "C04":
        return run.day_runners_count >= 3
    if c == "C05":
        return run.is_thursday_meeting
    if c == "C06":
        if not (run.is_group and run.group_size >= 2 and run.duration_min >= 30):
            return False
        others = [t for t in run.group_tiers if t != player.tier]
        if not others:
            return False
        return TIER_ORDER[player.tier] > min(TIER_ORDER[t] for t in others)
    if c == "C07":
        return run.is_group and len(set(run.group_tiers)) >= 2
    if c == "C08":
        return run.is_group and run.group_size >= 2 and run.duration_min >= 60 and run.is_easy
    if c == "C09":
        return run.is_group and run.group_size >= 2 and run.after_social

    return False


def d_distance_goal_km(tier: Tier) -> float:
    return {"beginner": 80.0, "intermediate": 150.0, "advanced": 250.0}[tier]


def update_player_with_run(player: PlayerState, run: RunEvent, *, season_cfg: SeasonConfig) -> list[str]:
    triggered: list[str] = []
    prev_day_ran = player.last_day_ran

    # per-run counters
    player.total_distance_km += run.distance_km
    player.weekly_run_counts[run.week_index] += 1

    if run.day_index >= (season_cfg.weeks * 7 - 7):
        player.final_week_runs += 1

    # day streak (only when it's first run of the day)
    if player.last_day_ran != run.day_index:
        if player.last_day_ran == run.day_index - 1:
            player.consecutive_days += 1
        else:
            player.consecutive_days = 1
        player.last_day_ran = run.day_index

        if "D01" in player.board["D"] and "D01" not in player.completed and player.consecutive_days >= 5:
            triggered.append("D01")
        if "D04" in player.board["D"] and "D04" not in player.completed and player.consecutive_days >= 3:
            triggered.append("D04")
        if prev_day_ran is not None and run.day_index - prev_day_ran == 2:
            if "D05" in player.board["D"] and "D05" not in player.completed:
                triggered.append("D05")

    if run.is_thursday_meeting:
        player.thursday_attendance += 1
        if (
            "W01" in player.board["W"]
            and "W01" not in player.completed
            and player.thursday_attendance >= season_cfg.w01_thu_needed
        ):
            triggered.append("W01")

    if run.is_bungae and run.is_host and run.group_size >= 3:
        player.hosted_bungae_3plus += 1
        if (
            "W02" in player.board["W"]
            and "W02" not in player.completed
            and player.hosted_bungae_3plus >= season_cfg.w02_host_needed
        ):
            triggered.append("W02")

    if "C06" in player.board["C"] or "W03" in player.board["W"]:
        # Pacemaker event is "C06 satisfied on this run".
        if run.is_group and run.duration_min >= 30 and check_card_satisfied("C06", player, run):
            player.pacemaker_count += 1
            if (
                "W03" in player.board["W"]
                and "W03" not in player.completed
                and player.pacemaker_count >= season_cfg.w03_pace_needed
            ):
                triggered.append("W03")

    if "D02" in player.board["D"] and "D02" not in player.completed and player.final_week_runs >= season_cfg.final_week_runs_needed:
        triggered.append("D02")

    if "D03" in player.board["D"] and "D03" not in player.completed and player.total_distance_km >= d_distance_goal_km(player.tier):
        triggered.append("D03")

    if "W04" in player.board["W"] and "W04" not in player.completed and player.weekly_run_counts[run.week_index] >= 6:
        triggered.append("W04")

    return triggered


def choose_checks(rng: random.Random, player: PlayerState, run: RunEvent, triggered: list[str]) -> list[str]:
    remaining = {t: [c for c in player.board[t] if c not in player.completed] for t in ["A", "B", "C", "D", "W"]}

    # Candidates for A/B/C based on run satisfaction.
    candidates: list[str] = []
    for t in ["A", "B", "C"]:
        if player.sealed_runs_left > 0 and player.sealed_type == t:
            continue
        satisfied = [c for c in remaining[t] if check_card_satisfied(c, player, run)]
        if not satisfied:
            continue
        best = max(satisfied, key=lambda code: (CARDS[code].stars, code))
        candidates.append(best)

    # Triggered D/W must be checked "now" in this simulator (aligns with "완성되는 러닝에서 체크").
    must = [c for c in triggered if c in remaining["D"] or c in remaining["W"]]
    must = sorted(must, key=lambda code: (CARDS[code].stars, code), reverse=True)

    picks: list[str] = []
    for code in must:
        if len(picks) >= 3:
            break
        picks.append(code)

    slots = 3 - len(picks)
    if slots <= 0:
        return picks

    # Choose up to N from A/B/C candidates by star priority.
    rest = sorted(candidates, key=lambda code: (CARDS[code].stars, code), reverse=True)
    picks.extend(rest[:slots])
    return picks


def maybe_apply_seals(rng: random.Random, players: list[PlayerState]) -> None:
    # Simplified Seal/Shield strategy:
    # - Token holders outside current Top3 try to Seal the current leader (if leader is ahead).
    # - If target has a token, they auto-use Shield (both tokens consumed, no seal applied).
    ranking = sorted(players, key=lambda p: (p.completed_count(), p.completed_star_sum()), reverse=True)
    if not ranking:
        return
    top3 = {p.name for p in ranking[:3]}
    leader = ranking[0]

    for attacker in players:
        if not attacker.has_token:
            continue
        if attacker.name in top3:
            continue
        if leader.completed_count() <= attacker.completed_count():
            continue
        if leader.sealed_runs_left > 0:
            continue
        if leader.name in attacker.seal_targets_used:
            continue

        remaining_b = sum(1 for c in leader.board["B"] if c not in leader.completed)
        remaining_c = sum(1 for c in leader.board["C"] if c not in leader.completed)
        seal_type: Literal["B", "C"] = "B" if remaining_b >= remaining_c else "C"

        attacker.has_token = False
        attacker.tokens_spent_seal += 1
        attacker.seal_targets_used.add(leader.name)
        if leader.has_token:
            leader.has_token = False
            leader.tokens_spent_shield += 1
            continue

        leader.sealed_type = seal_type
        leader.sealed_runs_left = 2
        leader.times_sealed += 1


def simulate_season(
    rng: random.Random,
    players: list[PlayerState],
    *,
    season_cfg: SeasonConfig,
    win_metric: Literal["completion", "stars", "hybrid"] = "completion",
    enable_seals: bool = False,
    token_mode: Literal["once", "recharge"] = "recharge",
) -> tuple[PlayerState, dict[str, object]]:
    day_count = season_cfg.weeks * 7

    for day_index in range(day_count):
        day_of_week = day_index % 7  # 0=Mon
        is_weekend = day_of_week in (5, 6)
        week_index = day_index // 7
        weather = sample_weather(rng)

        # Decide group events for the day.
        thursday_meeting = day_of_week == 3
        bungae_event = (not thursday_meeting) and (rng.random() < (0.22 if is_weekend else 0.10))

        thursday_participants: set[str] = set()
        bungae_participants: set[str] = set()
        bungae_host: str | None = None

        if thursday_meeting:
            target = rng.randint(season_cfg.thursday_participants_min, season_cfg.thursday_participants_max)
            target = min(target, len(players))
            # colder -> fewer participants (soft)
            if weather.feels_like_c <= -8.0:
                target = max(3, target - 2)
            weights = []
            for p in players:
                w = 1.0 + (0.2 * TIER_ORDER[p.tier])
                weights.append(w)
            pool = [p.name for p in players]
            picks = weighted_sample_without_replacement(rng, pool, weights, target)
            thursday_participants = set(picks)

        if bungae_event:
            target = rng.randint(2, 5)
            target = min(target, len(players))
            pool = [p.name for p in players]
            weights = []
            for p in players:
                # higher tiers host/join slightly more often
                w = 1.0 + (0.25 * TIER_ORDER[p.tier])
                weights.append(w)
            picks = weighted_sample_without_replacement(rng, pool, weights, target)
            bungae_participants = set(picks)
            bungae_host = rng.choice(list(bungae_participants)) if bungae_participants else None

        # Create run schedules (ensure event participants run).
        runs_by_player: dict[str, list[RunEvent]] = {}
        day_runners: set[str] = set()

        for p in players:
            tier_params = DEFAULT_TIER_PARAMS[p.tier]
            run_count = 1 if rng.random() < tier_params.p_run else 0
            if run_count and rng.random() < tier_params.p_two_a_day:
                run_count += 1

            in_thu = p.name in thursday_participants
            in_bungae = p.name in bungae_participants
            if (in_thu or in_bungae) and run_count == 0:
                run_count = 1

            if run_count == 0:
                runs_by_player[p.name] = []
                continue

            day_runners.add(p.name)
            events: list[RunEvent] = []
            for run_idx in range(run_count):
                is_group = False
                is_thu = False
                is_bungae = False
                is_host = False
                group_size = 1
                group_tiers: tuple[Tier, ...] = ()

                # First run of the day is group run if participating.
                if run_idx == 0 and in_thu:
                    is_group = True
                    is_thu = True
                    is_bungae = False
                    group_size = max(2, len(thursday_participants))
                    group_tiers = tuple(sorted((pl.tier for pl in players if pl.name in thursday_participants), key=TIER_ORDER.get))

                if run_idx == 0 and (not in_thu) and in_bungae:
                    is_group = True
                    is_bungae = True
                    group_size = max(2, len(bungae_participants))
                    group_tiers = tuple(sorted((pl.tier for pl in players if pl.name in bungae_participants), key=TIER_ORDER.get))
                    is_host = bungae_host == p.name

                is_easy = is_group and (rng.random() < 0.72)
                start_hour = sample_start_hour(rng, is_weekend=is_weekend, is_thursday_meeting=is_thu, is_group=is_group)

                duration_min, pace, distance_km = sample_run_metrics(rng, tier_params, is_group=is_group, is_easy=is_easy)

                is_track = (not is_group) and (rng.random() < (0.05 + 0.02 * TIER_ORDER[p.tier]))
                is_treadmill = rng.random() < (0.05 + (0.16 if weather.precipitation != "none" or weather.feels_like_c <= -6 else 0.0))

                if is_treadmill:
                    is_track = False

                if (not is_treadmill) and rng.random() < 0.26:
                    elevation_gain = rng.randint(60, 220)
                    hill_repeats = rng.randint(0, 6)
                else:
                    elevation_gain = rng.randint(0, 25)
                    hill_repeats = 0

                need_light = start_hour >= 18 or start_hour < 6
                has_light_gear = rng.random() < (0.6 if need_light else 0.18)

                did_warmup = rng.random() < (0.42 + 0.08 * TIER_ORDER[p.tier])
                did_cooldown = rng.random() < (0.52 + 0.08 * TIER_ORDER[p.tier])
                did_foam = rng.random() < (0.28 + 0.06 * TIER_ORDER[p.tier])
                did_strength = rng.random() < (0.22 + 0.07 * TIER_ORDER[p.tier])
                did_drills = rng.random() < (0.10 + 0.05 * TIER_ORDER[p.tier])
                did_log = rng.random() < 0.65
                is_new_route = rng.random() < 0.16
                is_build = rng.random() < (0.10 + 0.05 * TIER_ORDER[p.tier])
                with_new_runner = rng.random() < 0.08

                after_social = is_group and (rng.random() < 0.38)

                events.append(
                    RunEvent(
                        day_index=day_index,
                        week_index=week_index,
                        day_of_week=day_of_week,
                        start_hour=start_hour,
                        duration_min=duration_min,
                        pace_min_per_km=pace,
                        distance_km=distance_km,
                        weather=weather,
                        is_weekend=is_weekend,
                        is_track=is_track,
                        is_treadmill=is_treadmill,
                        elevation_gain_m=elevation_gain,
                        hill_repeats=hill_repeats,
                        has_light_gear=has_light_gear,
                        with_new_runner=with_new_runner,
                        did_warmup=did_warmup,
                        did_cooldown=did_cooldown,
                        did_foam_roll=did_foam,
                        did_strength=did_strength,
                        did_drills=did_drills,
                        did_log=did_log,
                        is_new_route=is_new_route,
                        is_build_up=is_build,
                        day_runners_count=0,  # filled later
                        is_group=is_group,
                        group_size=group_size,
                        group_tiers=group_tiers if group_tiers else (p.tier,),
                        is_thursday_meeting=is_thu,
                        is_bungae=is_bungae,
                        is_host=is_host,
                        after_social=after_social,
                        is_easy=is_easy,
                    )
                )
            runs_by_player[p.name] = events

        day_runners_count = len(day_runners)

        # Fill day_runners_count and play runs.
        for p in players:
            runs = runs_by_player[p.name]
            if not runs:
                continue
            for run_idx, run in enumerate(runs):
                run_with_day = dataclasses.replace(run, day_runners_count=day_runners_count)
                run_time = float(run_with_day.day_index * 24 + run_with_day.start_hour) + (0.01 * run_idx)
                triggered = update_player_with_run(p, run_with_day, season_cfg=season_cfg)
                checks = choose_checks(rng, p, run_with_day, triggered)
                for code in checks:
                    p.completed.add(code)
                checked_w = False
                for code in checks:
                    card = CARDS.get(code)
                    if card and card.card_type == "W":
                        checked_w = True
                        break
                if checked_w:
                    if token_mode == "recharge":
                        if not p.has_token:
                            p.has_token = True
                            p.tokens_earned += 1
                    else:
                        if not p.token_earned_once:
                            p.token_earned_once = True
                            p.has_token = True
                            p.tokens_earned += 1

                p.bingo_line_count = count_completed_lines(p.bingo_lines, p.completed) if p.bingo_lines else 0
                if p.five_bingo_time is None and p.bingo_line_count >= 5:
                    p.five_bingo_time = run_time

                if p.finish_time is None and p.completed_count() >= 25:
                    p.finish_time = run_time
                    if p.finished_day is None:
                        p.finished_day = day_index
                if p.sealed_runs_left > 0:
                    p.sealed_runs_left -= 1
                    if p.sealed_runs_left == 0:
                        p.sealed_type = None

        if enable_seals:
            maybe_apply_seals(rng, players)

    # Winners for each category.
    five_candidates = [p for p in players if p.five_bingo_time is not None]
    winner_5bingo = None
    if five_candidates:
        five_candidates.sort(key=lambda p: (p.five_bingo_time, -p.completed_star_sum(), -p.completed_count(), p.name))  # type: ignore[arg-type]
        winner_5bingo = five_candidates[0]

    finish_candidates = [p for p in players if p.finish_time is not None]
    winner_allbingo = None
    if finish_candidates:
        finish_candidates.sort(key=lambda p: (p.finish_time, -p.completed_star_sum(), p.name))  # type: ignore[arg-type]
        winner_allbingo = finish_candidates[0]

    winner_stars = max(players, key=lambda p: (p.completed_star_sum(), p.completed_count(), -(p.five_bingo_time or 10_000.0)))

    # Backward compatible "winner" for callers that still use win_metric.
    if win_metric == "stars":
        winner = winner_stars
    elif win_metric == "completion":
        winner = winner_allbingo or max(players, key=lambda p: (p.completed_count(), p.completed_star_sum()))
    else:
        winner = winner_allbingo or winner_stars

    summary: dict[str, object] = {
        "winner": winner.name,
        "winner_tier": winner.tier,
        "winner_completed": winner.completed_count(),
        "winner_finish_day": winner.finished_day,
        "winner_5bingo": winner_5bingo.name if winner_5bingo else None,
        "winner_5bingo_tier": winner_5bingo.tier if winner_5bingo else None,
        "winner_allbingo": winner_allbingo.name if winner_allbingo else None,
        "winner_allbingo_tier": winner_allbingo.tier if winner_allbingo else None,
        "winner_stars": winner_stars.name,
        "winner_stars_tier": winner_stars.tier,
    }
    return winner, summary


def parse_roster(path: str) -> list[tuple[str, Tier]]:
    raw = json.loads(open(path, "r", encoding="utf-8").read())
    if not isinstance(raw, list):
        raise ValueError("roster.json must be a list of {name,tier}")
    roster: list[tuple[str, Tier]] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"roster[{i}] must be an object")
        name = str(item.get("name", f"player{i+1}"))
        tier_raw = str(item.get("tier", "")).strip()
        if tier_raw not in TIER_ALIASES:
            raise ValueError(f"roster[{i}].tier invalid: {tier_raw}")
        roster.append((name, TIER_ALIASES[tier_raw]))
    return roster


def make_players(
    rng: random.Random,
    *,
    roster: list[tuple[str, Tier]] | None,
    beginners: int,
    intermediates: int,
    advanced: int,
    variant_w: bool,
    draft_mode: Literal["weighted", "random", "easiest"],
    alpha: float,
    min_star_sum: dict[Tier, int] | None = None,
) -> list[PlayerState]:
    players: list[PlayerState] = []
    if roster:
        for name, tier in roster:
            board = draft_board(
                rng,
                tier,
                variant_w=variant_w,
                draft_mode=draft_mode,
                alpha=alpha,
                min_star_sum=(min_star_sum or {}).get(tier),
            )
            grid, center_w = place_board(rng, board, tier=tier, variant_w=variant_w)
            players.append(
                PlayerState(
                    name=name,
                    tier=tier,
                    board=board,
                    grid=grid,
                    bingo_lines=build_bingo_lines(grid),
                    center_w_code=center_w,
                )
            )
        return players

    idx = 1
    for tier, count in [("beginner", beginners), ("intermediate", intermediates), ("advanced", advanced)]:
        for _ in range(count):
            name = f"{tier[:1].upper()}{idx:02d}"
            idx += 1
            board = draft_board(
                rng,
                tier,  # type: ignore[arg-type]
                variant_w=variant_w,
                draft_mode=draft_mode,
                alpha=alpha,
                min_star_sum=(min_star_sum or {}).get(tier),  # type: ignore[arg-type]
            )
            grid, center_w = place_board(rng, board, tier=tier, variant_w=variant_w)  # type: ignore[arg-type]
            players.append(
                PlayerState(
                    name=name,
                    tier=tier,  # type: ignore[arg-type]
                    board=board,
                    grid=grid,
                    bingo_lines=build_bingo_lines(grid),
                    center_w_code=center_w,
                )
            )

    return players


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Simulate a 4-week MRC bingo season (toy model).")
    parser.add_argument("--iterations", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--variant-w", action="store_true", help="Enable tier variants (intermediate W2, advanced W3).")
    parser.add_argument("--draft", choices=["weighted", "random", "easiest"], default="weighted")
    parser.add_argument("--alpha", type=float, default=0.9, help="Difficulty penalty for weighted draft (higher -> easier cards).")
    parser.add_argument("--win-metric", choices=["completion", "stars", "hybrid"], default="completion")
    parser.add_argument("--seals", action="store_true", help="Enable simplified Seal/Shield interactions.")
    parser.add_argument(
        "--token-mode",
        choices=["once", "recharge"],
        default="recharge",
        help="Token 획득 방식(once=시즌 1회, recharge=W 체크로 재획득).",
    )
    parser.add_argument("--w01-thu-needed", type=int, default=3, help="W01 달성에 필요한 목요미식회 횟수")
    parser.add_argument("--w02-host-needed", type=int, default=2, help="W02 달성에 필요한 3인+ 벙개 호스트 횟수")
    parser.add_argument("--w03-pace-needed", type=int, default=3, help="W03 달성에 필요한 페이스메이커 횟수")
    parser.add_argument(
        "--d02-final-week-runs",
        "--w04-final-week-runs",
        dest="final_week_runs_needed",
        type=int,
        default=6,
        help="D02 달성에 필요한 마지막 7일 러닝 횟수",
    )
    parser.add_argument("--min-star-beginner", type=int, default=0, help="Optional minimum total ★ sum for beginner boards (0 disables).")
    parser.add_argument("--min-star-intermediate", type=int, default=0, help="Optional minimum total ★ sum for intermediate boards (0 disables).")
    parser.add_argument("--min-star-advanced", type=int, default=0, help="Optional minimum total ★ sum for advanced boards (0 disables).")
    parser.add_argument("--beginners", type=int, default=7)
    parser.add_argument("--intermediates", type=int, default=6)
    parser.add_argument("--advanced", type=int, default=5)
    parser.add_argument("--roster", type=str, default="", help="Optional roster.json (list of {name,tier}).")

    args = parser.parse_args(argv)
    rng = random.Random(args.seed if args.seed != 0 else None)
    roster = parse_roster(args.roster) if args.roster else None

    season_cfg = SeasonConfig(
        weeks=4,
        final_week_runs_needed=args.final_week_runs_needed,
        w01_thu_needed=args.w01_thu_needed,
        w02_host_needed=args.w02_host_needed,
        w03_pace_needed=args.w03_pace_needed,
    )
    iterations = max(1, args.iterations)
    min_star_sum: dict[Tier, int] = {}
    if args.min_star_beginner:
        min_star_sum["beginner"] = args.min_star_beginner
    if args.min_star_intermediate:
        min_star_sum["intermediate"] = args.min_star_intermediate
    if args.min_star_advanced:
        min_star_sum["advanced"] = args.min_star_advanced

    wins_5bingo: dict[Tier, int] = {"beginner": 0, "intermediate": 0, "advanced": 0}
    wins_allbingo: dict[Tier, int] = {"beginner": 0, "intermediate": 0, "advanced": 0}
    wins_stars: dict[Tier, int] = {"beginner": 0, "intermediate": 0, "advanced": 0}
    none_5bingo = 0
    none_allbingo = 0

    per_tier_finish_days: dict[Tier, list[int]] = {"beginner": [], "intermediate": [], "advanced": []}
    per_tier_completed: dict[Tier, list[int]] = {"beginner": [], "intermediate": [], "advanced": []}
    per_tier_completed_star: dict[Tier, list[int]] = {"beginner": [], "intermediate": [], "advanced": []}
    per_tier_tokens: dict[Tier, list[int]] = {"beginner": [], "intermediate": [], "advanced": []}
    per_tier_seals_used: dict[Tier, list[int]] = {"beginner": [], "intermediate": [], "advanced": []}
    per_tier_shields_used: dict[Tier, list[int]] = {"beginner": [], "intermediate": [], "advanced": []}
    per_tier_times_sealed: dict[Tier, list[int]] = {"beginner": [], "intermediate": [], "advanced": []}

    for _ in range(iterations):
        players = make_players(
            rng,
            roster=roster,
            beginners=args.beginners,
            intermediates=args.intermediates,
            advanced=args.advanced,
            variant_w=bool(args.variant_w),
            draft_mode=args.draft,
            alpha=args.alpha,
            min_star_sum=min_star_sum or None,
        )
        _winner, summary = simulate_season(
            rng,
            players,
            season_cfg=season_cfg,
            win_metric=args.win_metric,
            enable_seals=bool(args.seals),
            token_mode=args.token_mode,
        )
        w5_tier = summary.get("winner_5bingo_tier")
        if w5_tier is None:
            none_5bingo += 1
        else:
            wins_5bingo[w5_tier] += 1  # type: ignore[index]

        wall_tier = summary.get("winner_allbingo_tier")
        if wall_tier is None:
            none_allbingo += 1
        else:
            wins_allbingo[wall_tier] += 1  # type: ignore[index]

        wins_stars[summary["winner_stars_tier"]] += 1  # type: ignore[index]

        for p in players:
            per_tier_completed[p.tier].append(p.completed_count())
            per_tier_completed_star[p.tier].append(p.completed_star_sum())
            per_tier_tokens[p.tier].append(p.tokens_earned)
            per_tier_seals_used[p.tier].append(p.tokens_spent_seal)
            per_tier_shields_used[p.tier].append(p.tokens_spent_shield)
            per_tier_times_sealed[p.tier].append(p.times_sealed)
            if p.finished_day is not None:
                per_tier_finish_days[p.tier].append(p.finished_day)

    def mean(xs: Iterable[int]) -> float:
        xs_list = list(xs)
        return float(statistics.mean(xs_list)) if xs_list else float("nan")

    def pct(n: int, d: int) -> float:
        return (100.0 * n / d) if d else 0.0

    print("=== MRC Bingo Season Simulator (toy model) ===")
    print(f"iterations: {iterations}")
    print(
        f"variant_w: {bool(args.variant_w)} | draft: {args.draft} | alpha: {args.alpha}"
        f" | win_metric: {args.win_metric}"
        f" | seals: {bool(args.seals)}"
        f" | token_mode: {args.token_mode}"
        f" | min_star: b{args.min_star_beginner}/i{args.min_star_intermediate}/a{args.min_star_advanced}"
    )
    if roster:
        print(f"roster: {args.roster} ({len(roster)} players)")
    else:
        total = args.beginners + args.intermediates + args.advanced
        print(f"players: {total} (beginner {args.beginners}, intermediate {args.intermediates}, advanced {args.advanced})")
    print("")

    print("Winners by category (tier win rate):")
    print(
        f"- 5bingo:    b {pct(wins_5bingo['beginner'], iterations):5.1f}%"
        f" | i {pct(wins_5bingo['intermediate'], iterations):5.1f}%"
        f" | a {pct(wins_5bingo['advanced'], iterations):5.1f}%"
        f" | none {pct(none_5bingo, iterations):5.1f}%"
    )
    print(
        f"- allbingo:  b {pct(wins_allbingo['beginner'], iterations):5.1f}%"
        f" | i {pct(wins_allbingo['intermediate'], iterations):5.1f}%"
        f" | a {pct(wins_allbingo['advanced'], iterations):5.1f}%"
        f" | none {pct(none_allbingo, iterations):5.1f}%"
    )
    print(
        f"- stars:     b {pct(wins_stars['beginner'], iterations):5.1f}%"
        f" | i {pct(wins_stars['intermediate'], iterations):5.1f}%"
        f" | a {pct(wins_stars['advanced'], iterations):5.1f}%"
    )
    print("")

    print("Tier stats:")
    for tier in ["beginner", "intermediate", "advanced"]:
        comp = per_tier_completed[tier]  # type: ignore[index]
        comp_star = per_tier_completed_star[tier]  # type: ignore[index]
        finish = per_tier_finish_days[tier]  # type: ignore[index]
        tokens = per_tier_tokens[tier]  # type: ignore[index]
        seals_used = per_tier_seals_used[tier]  # type: ignore[index]
        shields_used = per_tier_shields_used[tier]  # type: ignore[index]
        times_sealed = per_tier_times_sealed[tier]  # type: ignore[index]
        finish_rate = sum(1 for x in finish if x is not None)
        print(
            f"- {tier:12} | avg completed {mean(comp):5.1f}/25"
            f" | avg ★sum {mean(comp_star):5.1f}"
            f" | finish rate {pct(finish_rate, len(comp)):5.1f}%"
            f" | avg finish day {mean(finish) if finish else float('nan'):.1f}"
            f" | avg tokens {mean(tokens):4.2f}"
            f" | avg seals {mean(seals_used):4.2f}"
            f" | avg shields {mean(shields_used):4.2f}"
            f" | avg sealed {mean(times_sealed):4.2f}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
