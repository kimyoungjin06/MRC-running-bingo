from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from .label_map import build_label_map


NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


@dataclass(frozen=True)
class CardDef:
    code: str
    card_type: str
    stars: int
    title: str


def parse_carddeck(path: Path) -> dict[str, CardDef]:
    pattern = re.compile(r"^([ABCDW]\d{2})\s+(★+)\s+(.+)$")
    cards: dict[str, CardDef] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        m = pattern.match(line)
        if not m:
            continue
        code, stars, title = m.groups()
        cards[code] = CardDef(
            code=code,
            card_type=code[0],
            stars=len(stars),
            title=title.strip(),
        )
    return cards


def _parse_shared_strings(z: ZipFile) -> list[str]:
    shared_xml = z.read("xl/sharedStrings.xml")
    root = ET.fromstring(shared_xml)
    shared: list[str] = []
    for si in root.findall("s:si", NS):
        texts = [t.text or "" for t in si.findall(".//s:t", NS)]
        shared.append("".join(texts))
    return shared


def _cell_value(cell: ET.Element, shared: list[str]) -> str:
    value_node = cell.find("s:v", NS)
    if value_node is None:
        return ""
    value = value_node.text or ""
    if cell.get("t") == "s":
        try:
            return shared[int(value)]
        except (ValueError, IndexError):
            return ""
    return value


def _parse_sheet_rows(z: ZipFile) -> list[dict[str, str]]:
    sheet_xml = z.read("xl/worksheets/sheet1.xml")
    root = ET.fromstring(sheet_xml)
    shared = _parse_shared_strings(z)

    rows: list[dict[str, str]] = []
    for row in root.findall(".//s:row", NS):
        cells: dict[str, str] = {}
        for cell in row.findall("s:c", NS):
            ref = cell.get("r")
            if not ref:
                continue
            col = re.match(r"([A-Z]+)", ref)
            if not col:
                continue
            col_id = col.group(1)
            cells[col_id] = _cell_value(cell, shared)
        rows.append(cells)
    return rows


def _excel_serial_to_iso(value: str) -> str | None:
    try:
        serial = float(value)
    except (TypeError, ValueError):
        return None
    base = datetime(1899, 12, 30)
    dt = base + timedelta(days=serial)
    return dt.isoformat(timespec="seconds")


def _resolve_code(raw: str) -> str | None:
    m = re.search(r"([ABCDW]\d{2})", raw or "")
    return m.group(1) if m else None


def _normalize_tier(raw: str) -> tuple[str | None, str | None]:
    value = (raw or "").strip()
    if not value:
        return None, None
    normalized = value.lower()
    mapping = {
        "초보": "beginner",
        "중수": "intermediate",
        "고수": "advanced",
        "beginner": "beginner",
        "intermediate": "intermediate",
        "advanced": "advanced",
    }
    tier = mapping.get(value, mapping.get(normalized))
    return tier, value


def _stable_id(value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()
    return digest[:10]


def _map_code(code: str | None, label_map) -> tuple[str | None, str | None]:
    if not code:
        return None, None
    if not label_map:
        return code, None
    resolved = label_map.by_label.get(code, code)
    label = code if resolved != code else None
    return resolved, label


def _build_grid(
    row: dict[str, str],
    header_to_col: dict[str, str],
    cards: dict[str, CardDef],
    label_map,
) -> list[list[dict[str, Any]]]:
    grid: list[list[dict[str, Any]]] = []
    for r in range(1, 6):
        row_cells: list[dict[str, Any]] = []
        for c in range(1, 6):
            header = f"{r}행 {c}열"
            col = header_to_col.get(header)
            raw = row.get(col, "") if col else ""
            raw_code = _resolve_code(raw)
            code, label = _map_code(raw_code, label_map)
            card = cards.get(code) if code else None
            row_cells.append(
                {
                    "raw": raw.strip(),
                    "code": code,
                    "label": label,
                    "type": card.card_type if card else (raw_code[0] if raw_code else None),
                    "stars": card.stars if card else (raw.count("★") or None),
                    "title": card.title if card else None,
                }
            )
        grid.append(row_cells)
    return grid


def generate_boards_from_xlsx(
    input_path: Path,
    carddeck_path: Path,
    *,
    label_seed: str | None = None,
    use_label_map: bool = False,
) -> dict[str, Any]:
    if not input_path.exists():
        raise FileNotFoundError(f"input not found: {input_path}")
    if not carddeck_path.exists():
        raise FileNotFoundError(f"card deck not found: {carddeck_path}")

    cards = parse_carddeck(carddeck_path)
    label_map = build_label_map(label_seed) if (use_label_map and label_seed) else None

    with ZipFile(input_path) as z:
        rows = _parse_sheet_rows(z)

    if not rows:
        return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "boards": []}

    header_row = rows[0]
    header_to_col = {header: col for col, header in header_row.items()}

    boards = []
    for row in rows[1:]:
        name = row.get(header_to_col.get("이름", ""), "").strip()
        if not name:
            continue
        timestamp_raw = row.get(header_to_col.get("타임스탬프", ""), "")
        timestamp = _excel_serial_to_iso(timestamp_raw) or timestamp_raw or None
        email = row.get(header_to_col.get("이메일 주소", ""), "").strip() or None
        tier_raw = row.get(header_to_col.get("내 티어", ""), "").strip()
        tier, tier_label = _normalize_tier(tier_raw)

        player_id = f"player-{_stable_id(name + '|' + (email or ''))}"
        board_key = f"{name}|{timestamp_raw or ''}|{email or ''}"
        board_id = f"board-{_stable_id(board_key)}"
        grid = _build_grid(row, header_to_col, cards, label_map)
        boards.append(
            {
                "id": board_id,
                "player_id": player_id,
                "name": name,
                "timestamp": timestamp,
                "email": email,
                "tier": tier,
                "tier_label": tier_label,
                "grid": grid,
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": str(input_path),
        "code_basis": "actual" if use_label_map else "label",
        "label_map_applied": bool(use_label_map),
        "label_map_seed": label_seed if use_label_map else None,
        "boards": boards,
    }


def write_boards_json(data: dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _has_label_field(data: dict[str, Any]) -> bool:
    for board in data.get("boards", []) if isinstance(data, dict) else []:
        for row in (board or {}).get("grid", []):
            for cell in row or []:
                if isinstance(cell, dict) and "label" in cell:
                    return True
    return False


def apply_label_map_to_boards(
    data: dict[str, Any],
    *,
    label_seed: str,
    carddeck_path: Path,
) -> dict[str, Any]:
    if not isinstance(data, dict):
        return data
    if data.get("label_map_applied") or data.get("code_basis") == "actual" or _has_label_field(data):
        return data

    label_map = build_label_map(label_seed)
    cards = parse_carddeck(carddeck_path)

    out = json.loads(json.dumps(data, ensure_ascii=False))
    for board in out.get("boards", []):
        for row in (board or {}).get("grid", []):
            for cell in row or []:
                if not isinstance(cell, dict):
                    continue
                code = cell.get("code")
                if not code:
                    continue
                actual = label_map.by_label.get(code, code)
                if actual == code:
                    continue
                cell.setdefault("label", code)
                cell["code"] = actual
                card = cards.get(actual)
                if card:
                    cell["type"] = card.card_type
                    cell["stars"] = card.stars
                    cell["title"] = card.title

    out["label_map_applied"] = True
    out["code_basis"] = "actual"
    out["label_map_seed"] = label_seed
    return out


def load_boards_json(
    boards_path: Path,
    *,
    carddeck_path: Path | None,
    label_seed: str | None,
    apply_label_map: bool,
) -> dict[str, Any] | None:
    if not boards_path.exists():
        return None
    try:
        data = json.loads(boards_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if apply_label_map and carddeck_path and label_seed:
        return apply_label_map_to_boards(data, label_seed=label_seed, carddeck_path=carddeck_path)
    return data
