#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile


NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
DEFAULT_INPUT = Path("Data/🏃 퍼즐형 빙고 러닝 - 빙고판 수집 설문지(응답).xlsx")
DEFAULT_CARDDECK = Path("CardDeck.md")
DEFAULT_OUTPUT = Path("docs/data/boards.json")


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


def parse_shared_strings(z: ZipFile) -> list[str]:
    shared_xml = z.read("xl/sharedStrings.xml")
    root = ET.fromstring(shared_xml)
    shared: list[str] = []
    for si in root.findall("s:si", NS):
        texts = [t.text or "" for t in si.findall(".//s:t", NS)]
        shared.append("".join(texts))
    return shared


def cell_value(cell: ET.Element, shared: list[str]) -> str:
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


def parse_sheet_rows(z: ZipFile) -> list[dict[str, str]]:
    sheet_xml = z.read("xl/worksheets/sheet1.xml")
    root = ET.fromstring(sheet_xml)
    shared = parse_shared_strings(z)

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
            cells[col_id] = cell_value(cell, shared)
        rows.append(cells)
    return rows


def excel_serial_to_iso(value: str) -> str | None:
    try:
        serial = float(value)
    except (TypeError, ValueError):
        return None
    base = datetime(1899, 12, 30)
    dt = base + timedelta(days=serial)
    return dt.isoformat(timespec="seconds")


def resolve_code(raw: str) -> str | None:
    m = re.search(r"([ABCDW]\d{2})", raw or "")
    return m.group(1) if m else None


def stable_id(value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()
    return digest[:10]


def build_board_entry(
    *,
    name: str,
    timestamp: str | None,
    email: str | None,
    player_id: str,
    board_id: str,
    grid: list[list[dict[str, Any]]],
) -> dict[str, Any]:
    return {
        "id": board_id,
        "player_id": player_id,
        "name": name,
        "timestamp": timestamp,
        "email": email,
        "grid": grid,
    }


def build_grid(row: dict[str, str], header_to_col: dict[str, str], cards: dict[str, CardDef]) -> list[list[dict[str, Any]]]:
    grid: list[list[dict[str, Any]]] = []
    for r in range(1, 6):
        row_cells: list[dict[str, Any]] = []
        for c in range(1, 6):
            header = f"{r}행 {c}열"
            col = header_to_col.get(header)
            raw = row.get(col, "") if col else ""
            code = resolve_code(raw)
            card = cards.get(code) if code else None
            row_cells.append(
                {
                    "raw": raw.strip(),
                    "code": code,
                    "type": card.card_type if card else (code[0] if code else None),
                    "stars": card.stars if card else (raw.count("★") or None),
                    "title": card.title if card else None,
                }
            )
        grid.append(row_cells)
    return grid


def generate_boards(input_path: Path, carddeck_path: Path) -> dict[str, Any]:
    if not input_path.exists():
        raise FileNotFoundError(f"input not found: {input_path}")
    if not carddeck_path.exists():
        raise FileNotFoundError(f"card deck not found: {carddeck_path}")

    cards = parse_carddeck(carddeck_path)

    with ZipFile(input_path) as z:
        rows = parse_sheet_rows(z)

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
        timestamp = excel_serial_to_iso(timestamp_raw) or timestamp_raw or None
        email = row.get(header_to_col.get("이메일 주소", ""), "").strip() or None

        player_id = f"player-{stable_id(name + '|' + (email or ''))}"
        board_key = f"{name}|{timestamp_raw or ''}|{email or ''}"
        board_id = f"board-{stable_id(board_key)}"
        grid = build_grid(row, header_to_col, cards)
        boards.append(
            build_board_entry(
                name=name,
                timestamp=timestamp,
                email=email,
                player_id=player_id,
                board_id=board_id,
                grid=grid,
            )
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": str(input_path),
        "boards": boards,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate bingo boards JSON from Google Form responses (xlsx).")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input xlsx file path")
    parser.add_argument("--carddeck", type=Path, default=DEFAULT_CARDDECK, help="CardDeck.md path")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output JSON path")
    args = parser.parse_args()

    data = generate_boards(args.input, args.carddeck)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(data.get('boards', []))} boards to {args.output}")


if __name__ == "__main__":
    main()
