from __future__ import annotations

from dataclasses import dataclass

from .cards import CARDS_BY_TYPE


def hash_string_fnv1a_32(value: str) -> int:
    h = 2166136261
    for ch in value:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h & 0xFFFFFFFF


def mulberry32(seed: int):
    seed &= 0xFFFFFFFF

    def next_float() -> float:
        nonlocal seed
        seed = (seed + 0x6D2B79F5) & 0xFFFFFFFF
        t = seed
        t = (t ^ (t >> 15)) & 0xFFFFFFFF
        t = (t * ((t | 1) & 0xFFFFFFFF)) & 0xFFFFFFFF
        t2 = (t ^ (t >> 7)) & 0xFFFFFFFF
        t2 = (t2 * ((t | 61) & 0xFFFFFFFF)) & 0xFFFFFFFF
        t = (t ^ ((t + t2) & 0xFFFFFFFF)) & 0xFFFFFFFF
        t = (t ^ (t >> 14)) & 0xFFFFFFFF
        return t / 4294967296

    return next_float


def shuffle_in_place(items: list[str], rng) -> None:
    for i in range(len(items) - 1, 0, -1):
        j = int(rng() * (i + 1))
        items[i], items[j] = items[j], items[i]


@dataclass(frozen=True)
class LabelMap:
    seed: str
    by_id: dict[str, str]  # mission id -> back label
    by_label: dict[str, str]  # back label -> mission id


def build_label_map(seed: str) -> LabelMap:
    rng = mulberry32(hash_string_fnv1a_32(seed))
    by_id: dict[str, str] = {}
    by_label: dict[str, str] = {}

    for card_type in ("A", "B", "C", "D", "W"):
        codes = list(CARDS_BY_TYPE[card_type])  # sorted
        labels = list(codes)
        shuffle_in_place(labels, rng)
        for code, label in zip(codes, labels, strict=False):
            by_id[code] = label
            by_label[label] = code

    return LabelMap(seed=seed, by_id=by_id, by_label=by_label)
