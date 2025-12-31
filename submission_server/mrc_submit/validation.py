from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
import re
from typing import Literal

from .cards import CARDS, TIER_ALIASES, CardType, Tier


ValidationStatus = Literal["passed", "failed", "needs_review"]


@dataclass(frozen=True)
class RunPayload:
    tier: Tier
    run_date: date | None
    start_time: time | None
    distance_km: float | None
    duration_min: int | None
    temperature_c: float | None
    feels_like_c: float | None
    wind_m_s: float | None
    precipitation: Literal["none", "rain", "snow"]

    is_track: bool
    is_treadmill: bool
    elevation_gain_m: int | None
    hill_repeats: int | None
    has_light_gear: bool

    is_silent: bool
    with_new_runner: bool
    did_warmup: bool
    did_cooldown: bool
    did_foam_roll: bool
    did_strength: bool
    did_drills: bool
    did_log: bool
    is_new_route: bool
    is_build_up: bool

    is_group: bool
    group_size: int | None
    group_tiers: tuple[Tier, ...] | None
    day_runners_count: int | None
    is_thursday_meeting: bool
    is_bungae: bool
    is_host: bool
    after_social: bool
    is_easy: bool


def normalize_tier(value: str) -> Tier:
    raw = (value or "").strip()
    if raw in TIER_ALIASES:
        return TIER_ALIASES[raw]
    if raw.lower() in TIER_ALIASES:
        return TIER_ALIASES[raw.lower()]
    raise ValueError("invalid tier")


def tier_value(tier: Tier, beginner: float, intermediate: float, advanced: float) -> float:
    if tier == "beginner":
        return beginner
    if tier == "intermediate":
        return intermediate
    return advanced


def _check_ge(value: float | int | None, threshold: float, *, label: str) -> tuple[ValidationStatus, list[str]]:
    if value is None:
        return "needs_review", [f"{label} 입력 필요"]
    if float(value) >= threshold:
        return "passed", []
    return "failed", [f"{label} 부족: {value} < {threshold}"]


def _check_bool(value: bool, *, label: str) -> tuple[ValidationStatus, list[str]]:
    if value:
        return "passed", []
    return "failed", [f"{label} 미충족"]


def _merge_status(*statuses: ValidationStatus) -> ValidationStatus:
    if "failed" in statuses:
        return "failed"
    if "needs_review" in statuses:
        return "needs_review"
    return "passed"


def _merge_reasons(*groups: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for reasons in groups:
        for reason in reasons:
            if reason in seen:
                continue
            seen.add(reason)
            out.append(reason)
    return out


def _check_base_run(run: RunPayload) -> tuple[ValidationStatus, list[str]]:
    distance_status, distance_reasons = _check_ge(
        run.distance_km,
        tier_value(run.tier, 5.0, 7.0, 10.0),
        label="거리(km)",
    )
    duration_status, duration_reasons = _check_ge(
        run.duration_min,
        tier_value(run.tier, 30.0, 40.0, 50.0),
        label="시간(분)",
    )
    status = _merge_status(distance_status, duration_status)
    reasons = _merge_reasons(distance_reasons, duration_reasons)
    return status, reasons


def _start_hour(run: RunPayload) -> int | None:
    if run.start_time is None:
        return None
    return int(run.start_time.hour)


def evaluate_card(card_code: str, run: RunPayload) -> tuple[ValidationStatus, list[str]]:
    if card_code not in CARDS:
        return "failed", ["알 수 없는 카드 코드"]

    card = CARDS[card_code]
    c = card_code
    base_status, base_reasons = _check_base_run(run)
    if c == "A10":
        base_status, base_reasons = "passed", []

    def finalize(status: ValidationStatus, reasons: list[str]) -> tuple[ValidationStatus, list[str]]:
        return _merge_status(base_status, status), _merge_reasons(base_reasons, reasons)

    if card.card_type in ("D", "W"):
        return finalize("needs_review", ["누적/시즌 조건: 자동 판정 보류(운영진 확인 필요)"])

    if c == "A01":
        return finalize(
            *_check_ge(run.distance_km, tier_value(run.tier, 5.0, 7.0, 10.0), label="거리(km)")
        )
    if c == "A02":
        return finalize(
            *_check_ge(run.distance_km, tier_value(run.tier, 6.0, 8.0, 12.0), label="거리(km)")
        )
    if c == "A03":
        return finalize(
            *_check_ge(run.distance_km, tier_value(run.tier, 7.0, 10.0, 15.0), label="거리(km)")
        )
    if c == "A04":
        return finalize(
            *_check_ge(run.duration_min, tier_value(run.tier, 30.0, 40.0, 50.0), label="시간(분)")
        )
    if c == "A05":
        return finalize(
            *_check_ge(run.duration_min, tier_value(run.tier, 50.0, 60.0, 70.0), label="시간(분)")
        )
    if c == "A06":
        return finalize(*_check_bool(run.did_warmup, label="워밍업"))
    if c == "A07":
        return finalize(*_check_bool(run.did_cooldown, label="쿨다운 스트레칭"))
    if c == "A08":
        return finalize(*_check_bool(run.did_foam_roll, label="폼롤링/마사지"))
    if c == "A09":
        return finalize(*_check_bool(run.did_strength, label="보강운동"))
    if c == "A10":
        status, reasons = _check_ge(run.distance_km, 5.0, label="거리(km)")
        if status != "passed":
            return finalize(status, reasons)
        status, reasons = _check_bool(run.with_new_runner, label="첫 러닝 동행")
        return finalize(status, reasons)
    if c == "A11":
        status, reasons = _check_ge(run.distance_km, tier_value(run.tier, 5.0, 7.0, 10.0), label="거리(km)")
        if status != "passed":
            return finalize(status, reasons)
        status, reasons = _check_bool(run.is_new_route, label="새 코스")
        return finalize(status, reasons)
    if c == "A12":
        status, reasons = _check_ge(run.duration_min, tier_value(run.tier, 30.0, 40.0, 50.0), label="시간(분)")
        if status != "passed":
            return finalize(status, reasons)
        status, reasons = _check_bool(run.is_build_up, label="빌드업/네거티브")
        return finalize(status, reasons)
    if c == "A13":
        return finalize(*_check_bool(run.did_drills, label="러닝 드릴"))
    if c == "A14":
        return finalize(*_check_bool(run.did_log, label="인스타 공유"))

    if c == "B01":
        h = _start_hour(run)
        if h is None:
            return finalize("needs_review", ["시작 시간 입력 필요"])
        if h >= 22:
            return finalize("passed", [])
        return finalize("failed", [f"시작 시간이 22시 이전({h}시)"])
    if c == "B02":
        h = _start_hour(run)
        if h is None:
            return finalize("needs_review", ["시작 시간 입력 필요"])
        if h < 6:
            return finalize("passed", [])
        return finalize("failed", [f"시작 시간이 6시 이후({h}시)"])
    if c == "B03":
        if run.temperature_c is None:
            return finalize("needs_review", ["기온 입력 필요"])
        if run.temperature_c <= 0.0:
            return finalize("passed", [])
        return finalize("failed", [f"기온이 0°C 초과({run.temperature_c}°C)"])
    if c == "B04":
        if run.precipitation in ("rain", "snow"):
            return finalize("passed", [])
        return finalize("failed", ["강수(비/눈) 아님"])
    if c == "B05":
        if run.run_date is None:
            return finalize("needs_review", ["날짜 입력 필요"])
        is_weekend = run.run_date.weekday() >= 5
        if is_weekend:
            return finalize("passed", [])
        return finalize("failed", ["주말(토/일) 아님"])
    if c == "B06":
        if run.feels_like_c is None and run.wind_m_s is None:
            return finalize("needs_review", ["체감온도 또는 풍속 입력 필요"])
        feels_ok = (run.feels_like_c is not None) and (run.feels_like_c <= -5.0)
        wind_ok = (run.wind_m_s is not None) and (run.wind_m_s >= 6.0)
        if feels_ok or wind_ok:
            return finalize("passed", [])
        return finalize("failed", ["한파/강풍 조건 미달"])
    if c == "B07":
        if run.elevation_gain_m is None and run.hill_repeats is None:
            return finalize("needs_review", ["고도상승 또는 언덕 반복 입력 필요"])
        gain_ok = (run.elevation_gain_m is not None) and (run.elevation_gain_m >= 100)
        rep_ok = (run.hill_repeats is not None) and (run.hill_repeats >= 3)
        if gain_ok or rep_ok:
            return finalize("passed", [])
        return finalize("failed", ["언덕 조건 미달"])
    if c == "B08":
        return finalize(*_check_bool(run.is_track, label="트랙"))
    if c == "B09":
        return finalize(*_check_bool(run.is_treadmill, label="트레드밀"))
    if c == "B10":
        return finalize(*_check_bool(run.has_light_gear, label="반사/라이트 장비"))

    if c == "C01":
        if run.group_size is None:
            return finalize("needs_review", ["그룹 인원 입력 필요"])
        if run.group_size >= 2:
            return finalize("passed", [])
        return finalize("failed", ["그룹 인원 2명 미만"])
    if c == "C02":
        if run.group_size is None:
            return finalize("needs_review", ["그룹 인원 입력 필요"])
        if not run.is_bungae:
            return finalize("failed", ["벙개 아님"])
        if not run.is_host:
            return finalize("failed", ["호스트 아님"])
        if run.group_size >= 2:
            return finalize("passed", [])
        return finalize("failed", ["그룹 인원 2명 미만"])
    if c == "C03":
        if run.group_size is None:
            return finalize("needs_review", ["그룹 인원 입력 필요"])
        if run.duration_min is None:
            return finalize("needs_review", ["시간(분) 입력 필요"])
        ok = run.group_size >= 2 and run.duration_min >= 20
        if ok:
            return finalize("passed", [])
        return finalize("failed", ["2인 동행 20분+ 조건 미달"])
    if c == "C04":
        if run.day_runners_count is None:
            return finalize("needs_review", ["당일 인증 인원 입력 필요"])
        if run.day_runners_count >= 3:
            return finalize("passed", [])
        return finalize("failed", ["3명 이상 인증 조건 미달"])
    if c == "C05":
        return finalize(*_check_bool(run.is_thursday_meeting, label="목요미식회"))
    if c == "C06":
        if run.group_size is None:
            return finalize("needs_review", ["그룹 인원 입력 필요"])
        if run.duration_min is None:
            return finalize("needs_review", ["시간(분) 입력 필요"])
        if run.group_tiers is None or not run.group_tiers:
            return finalize("needs_review", ["그룹 티어 정보 입력 필요"])
        if not (run.group_size >= 2 and run.duration_min >= 30):
            return finalize("failed", ["30분+ 동행 조건 미달"])
        others = [t for t in run.group_tiers if t != run.tier]
        if not others:
            return finalize("failed", ["다른 티어 러너 없음"])
        order = {"beginner": 0, "intermediate": 1, "advanced": 2}
        is_pacemaker = order[run.tier] > min(order[t] for t in others)
        return finalize(
            ("passed", []) if is_pacemaker else ("failed", ["페이스메이킹(나보다 느린 러너) 조건 미달"])
        )
    if c == "C07":
        if run.group_tiers is None or not run.group_tiers:
            return finalize("needs_review", ["그룹 티어 정보 입력 필요"])
        return finalize(
            ("passed", []) if len(set(run.group_tiers)) >= 2 else ("failed", ["서로 다른 티어 2인+ 조건 미달"])
        )
    if c == "C08":
        if run.group_size is None:
            return finalize("needs_review", ["그룹 인원 입력 필요"])
        if run.duration_min is None:
            return finalize("needs_review", ["시간(분) 입력 필요"])
        ok = run.group_size >= 2 and run.duration_min >= 60 and run.is_easy
        if ok:
            return finalize("passed", [])
        return finalize("failed", ["2인+ 60분+ 회복페이스 조건 미달"])
    if c == "C09":
        if run.group_size is None:
            return finalize("needs_review", ["그룹 인원 입력 필요"])
        ok = run.group_size >= 2 and run.after_social
        if ok:
            return finalize("passed", [])
        return finalize("failed", ["2인+ 함께(스트레칭/커피) 조건 미달"])

    return finalize("needs_review", [f"자동 판정 규칙 없음: {card.card_type}"])


def validate_claim_labels(labels: list[str]) -> tuple[bool, list[str]]:
    messages: list[str] = []
    clean = normalize_claim_labels(labels)
    if len(clean) == 0:
        return False, ["체크할 카드 코드(라벨)를 1개 이상 입력하세요."]
    if len(set(clean)) != len(clean):
        messages.append("중복 카드가 포함되어 있어요(중복 제거 필요).")

    invalid = [label for label in clean if not re.fullmatch(r"[ABCDW]\d{2}", label)]
    if invalid:
        messages.append(f"카드 코드 형식이 올바르지 않아요: {', '.join(invalid)}")

    if len(clean) > 3:
        return False, ["러닝 1회당 최대 3칸까지만 체크할 수 있어요."]

    type_counts: dict[CardType, int] = {"A": 0, "B": 0, "C": 0, "D": 0, "W": 0}
    for label in clean:
        t = label[0]
        if t not in type_counts:
            messages.append(f"알 수 없는 타입: {label}")
            continue
        type_counts[t] += 1

    if type_counts["A"] > 1:
        messages.append("같은 러닝에서 A(Base)는 최대 1칸만 가능해요.")
    if type_counts["B"] > 1:
        messages.append("같은 러닝에서 B(Condition)은 최대 1칸만 선택 가능해요.")
    if type_counts["C"] > 1:
        messages.append("같은 러닝에서 C(Co-op)는 최대 1칸만 선택 가능해요.")

    ok = len(messages) == 0
    return ok, messages


def normalize_claim_labels(labels: list[str]) -> list[str]:
    normalized: list[str] = []
    for label in labels:
        value = normalize_label(label)
        if value:
            normalized.append(value)
    return normalized


def normalize_label(value: str | None) -> str | None:
    raw = (value or "").strip().upper().replace(" ", "")
    if not raw:
        return None
    m = re.fullmatch(r"([ABCDW])(\d{1,2})", raw)
    if not m:
        return raw
    return f"{m.group(1)}{m.group(2).zfill(2)}"
