from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .boards import load_boards_json
from .cards import CARDS, TIER_ALIASES
from .llm import preprocess_submission
from .storage import Storage


def _parse_time(value: str, default: dt_time) -> dt_time:
    raw = (value or "").strip()
    if not raw:
        return default
    try:
        hour, minute = raw.split(":", 1)
        return dt_time(int(hour), int(minute))
    except (ValueError, TypeError):
        return default


def _cutoff_window(now: datetime, cutoff: dt_time) -> tuple[datetime, datetime]:
    target_date = now.date()
    if now.timetz() < cutoff:
        target_date -= timedelta(days=1)
    window_end = datetime.combine(target_date, cutoff, tzinfo=now.tzinfo)
    window_start = window_end - timedelta(hours=24)
    return window_start, window_end


def _load_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_state(state_path: Path, state: dict[str, Any]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _iso_to_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _stable_id(value: str) -> str:
    import hashlib

    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()
    return digest[:10]


def _normalize_tier(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if raw in TIER_ALIASES:
        return TIER_ALIASES[raw]
    if raw.lower() in TIER_ALIASES:
        return TIER_ALIASES[raw.lower()]
    return None


def _token_cap(tier: str | None) -> int:
    return {"beginner": 1, "intermediate": 2, "advanced": 3}.get(tier or "", 1)


def _read_boards(boards_path: Path) -> dict[str, Any] | None:
    if not boards_path.exists():
        return None
    try:
        return json.loads(boards_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def run_preprocess(*, storage_dir: Path, tz: ZoneInfo, cutoff: dt_time) -> Path:
    db_path = storage_dir / "index.sqlite"
    state_path = storage_dir / "state.json"
    now = datetime.now(tz)
    window_start, window_end = _cutoff_window(now, cutoff)
    window_start_utc = window_start.astimezone(timezone.utc)
    window_end_utc = window_end.astimezone(timezone.utc)

    items: list[dict[str, Any]] = []
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT
              id, created_at, player_name, tier, run_date, start_time,
              distance_km, duration_min, claimed_labels_json, resolved_codes_json,
              validation_json, notes, token_event, token_hold, seal_target, seal_type,
              log_summary, review_status
            FROM submissions
            WHERE created_at >= ? AND created_at < ?
            ORDER BY created_at ASC
            """,
            (window_start_utc.isoformat(), window_end_utc.isoformat()),
        ).fetchall()

        for row in rows:
            payload = {
                "id": row["id"],
                "created_at": row["created_at"],
                "player_name": row["player_name"],
                "tier": row["tier"],
                "run_date": row["run_date"],
                "start_time": row["start_time"],
                "distance_km": row["distance_km"],
                "duration_min": row["duration_min"],
                "claimed_labels": json.loads(row["claimed_labels_json"] or "[]"),
                "resolved_codes": json.loads(row["resolved_codes_json"] or "[]"),
                "validation": json.loads(row["validation_json"] or "{}"),
                "notes": row["notes"],
                "token": {
                    "event": row["token_event"],
                    "hold": row["token_hold"],
                    "seal_target": row["seal_target"],
                    "seal_type": row["seal_type"],
                    "log_summary": row["log_summary"],
                },
                "review_status": row["review_status"] or "pending",
            }
            llm_result = preprocess_submission(payload)
            items.append(
                {
                    "submission": payload,
                    "llm": llm_result,
                }
            )
            if row["review_status"] is None:
                con.execute(
                    "UPDATE submissions SET review_status = 'pending' WHERE id = ? AND review_status IS NULL",
                    (row["id"],),
                )
        con.commit()
    finally:
        con.close()

    out_dir = storage_dir / "preprocess"
    out_dir.mkdir(parents=True, exist_ok=True)
    label = window_start.date().isoformat()
    out_path = out_dir / f"{label}.json"
    out_path.write_text(
        json.dumps(
            {
                "generated_at": now.isoformat(),
                "window": {"start": window_start.isoformat(), "end": window_end.isoformat()},
                "items": items,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    state = _load_state(state_path)
    state["last_preprocess"] = now.isoformat()
    _save_state(state_path, state)
    return out_path


def _board_lines(grid: list[list[str | None]]) -> list[list[str]]:
    lines: list[list[str]] = []
    if len(grid) != 5 or any(len(row) != 5 for row in grid):
        return lines
    for row in grid:
        if all(row):
            lines.append([c for c in row if c])
    for col in range(5):
        col_vals = [grid[row][col] for row in range(5)]
        if all(col_vals):
            lines.append([c for c in col_vals if c])
    diag1 = [grid[i][i] for i in range(5)]
    diag2 = [grid[i][4 - i] for i in range(5)]
    if all(diag1):
        lines.append([c for c in diag1 if c])
    if all(diag2):
        lines.append([c for c in diag2 if c])
    return lines


def run_publish(*, storage_dir: Path, tz: ZoneInfo, seed: str) -> Path:
    db_path = storage_dir / "index.sqlite"
    state_path = storage_dir / "state.json"
    now = datetime.now(tz)

    boards_path = Path(os.getenv("MRC_BOARDS_PATH") or (storage_dir / "boards" / "boards.json"))
    carddeck_path = Path(os.getenv("MRC_CARDDECK_PATH", str(Path(__file__).resolve().parents[1] / "CardDeck.md")))
    map_labels = (os.getenv("MRC_BOARD_LABEL_MAP") or "").strip().lower() in ("1", "true", "yes", "on")
    boards_data = load_boards_json(
        boards_path,
        carddeck_path=carddeck_path,
        label_seed=seed,
        apply_label_map=map_labels,
    ) or {}
    board_index: dict[str, dict[str, Any]] = {}
    board_tiers: dict[str, str] = {}
    for board in boards_data.get("boards", []) if isinstance(boards_data, dict) else []:
        if not board:
            continue
        name = board.get("name")
        if not name:
            continue
        board_index[name] = board
        board_tier = _normalize_tier(board.get("tier") or board.get("tier_label"))
        if board_tier:
            board_tiers[name] = board_tier

    board_lines_by_name: dict[str, list[list[str]]] = {}
    board_codes_by_name: dict[str, set[str]] = {}
    for name, board in board_index.items():
        grid = [
            [cell.get("code") if cell else None for cell in row_cells]
            for row_cells in board.get("grid", [])
        ]
        board_lines_by_name[name] = _board_lines(grid)
        board_codes_by_name[name] = {
            cell.get("code")
            for row_cells in board.get("grid", [])
            for cell in row_cells
            if cell and cell.get("code")
        }

    w_codes = {code for code, card in CARDS.items() if card.card_type == "W"}
    players: dict[str, dict[str, Any]] = {}
    attack_logs: list[dict[str, Any]] = []
    latest_logs: list[dict[str, Any]] = []

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT
              id, created_at, player_name, tier, resolved_codes_json,
              token_event, token_hold, seal_target, seal_type, log_summary,
              review_status, review_cards_json
            FROM submissions
            WHERE review_status IN ('approved', 'pending')
            ORDER BY created_at ASC
            """
        ).fetchall()

        for row in rows:
            name = row["player_name"]
            if not name:
                continue
            player = players.setdefault(
                name,
                {
                    "id": f"player-{_stable_id(name)}",
                    "name": name,
                    "tier": board_tiers.get(name) or row["tier"],
                    "codes": set(),
                    "w_codes": set(),
                    "token_used": 0,
                    "last_update": None,
                    "bingo5_at": None,
                    "full_at": None,
                },
            )

            created_at = _iso_to_dt(row["created_at"])
            created_local = created_at.astimezone(tz).isoformat() if created_at else row["created_at"]
            if created_at and (player["last_update"] is None or created_at > player["last_update"]):
                player["last_update"] = created_at

            codes = json.loads(row["resolved_codes_json"] or "[]")
            try:
                review_cards = json.loads(row["review_cards_json"] or "{}")
            except json.JSONDecodeError:
                review_cards = {}
            if review_cards:
                approved_codes = [code for code, status in review_cards.items() if status == "approved"]
            elif row["review_status"] != "approved":
                approved_codes = []
            else:
                approved_codes = codes
            codes = approved_codes
            board_codes = board_codes_by_name.get(name)
            if board_codes:
                codes = [c for c in codes if c in board_codes]
            player["codes"].update(codes)
            player["w_codes"].update(code for code in codes if code in w_codes)

            if created_at:
                board_lines = board_lines_by_name.get(name)
                if board_lines and player["bingo5_at"] is None:
                    checked = player["codes"]
                    bingo_count = sum(1 for line in board_lines if all(code in checked for code in line))
                    if bingo_count >= 5:
                        player["bingo5_at"] = created_at
                if board_codes and player["full_at"] is None:
                    checked = player["codes"]
                    if len(checked & board_codes) >= len(board_codes):
                        player["full_at"] = created_at

            if row["review_status"] == "approved" and row["token_event"] in ("seal", "shield"):
                player["token_used"] += 1

            if row["token_event"] == "seal":
                attack_logs.append(
                    {
                        "time": created_local,
                        "actor": name,
                        "target": row["seal_target"],
                        "seal_type": row["seal_type"],
                    }
                )
            if row["log_summary"]:
                latest_logs.append(
                    {
                        "time": created_local,
                        "player": name,
                        "message": row["log_summary"],
                    }
                )
    finally:
        con.close()

    bingo5_times = {name: player.get("bingo5_at") for name, player in players.items() if player.get("bingo5_at")}
    full_times = {name: player.get("full_at") for name, player in players.items() if player.get("full_at")}
    first_bingo5_at = min(bingo5_times.values()) if bingo5_times else None
    first_full_at = min(full_times.values()) if full_times else None
    first_bingo5_names = {name for name, dt in bingo5_times.items() if dt == first_bingo5_at}
    first_full_names = {name for name, dt in full_times.items() if dt == first_full_at}

    players_out: list[dict[str, Any]] = []
    token_holds: list[dict[str, Any]] = []

    for name, player in players.items():
        checked_codes = sorted(player["codes"])
        stars = sum(CARDS[code].stars for code in checked_codes if code in CARDS)
        board = board_index.get(name)
        bingo = 0
        if board:
            grid = [
                [cell.get("code") if cell else None for cell in row_cells]
                for row_cells in board.get("grid", [])
            ]
            lines = _board_lines(grid)
            checked = set(checked_codes)
            bingo = sum(1 for line in lines if all(code in checked for code in line))
        last_update = player["last_update"].astimezone(tz).isoformat() if player["last_update"] else None
        bingo5_at = player.get("bingo5_at")
        full_at = player.get("full_at")
        bingo5_at_local = bingo5_at.astimezone(tz).isoformat() if bingo5_at else None
        full_at_local = full_at.astimezone(tz).isoformat() if full_at else None
        earned = len(player.get("w_codes") or [])
        token_cap = _token_cap(player.get("tier"))
        tokens = max(0, min(token_cap, earned - (player.get("token_used") or 0)))
        players_out.append(
            {
                "id": board.get("player_id") if board else player["id"],
                "name": name,
                "checked": len(checked_codes),
                "bingo": bingo,
                "stars": stars,
                "tokens": tokens,
                "token_cap": token_cap,
                "last_update": last_update,
                "checked_codes": checked_codes,
                "achievements": {
                    "bingo5": bool(bingo5_at),
                    "bingo5_at": bingo5_at_local,
                    "full": bool(full_at),
                    "full_at": full_at_local,
                    "first_bingo5": name in first_bingo5_names,
                    "first_full": name in first_full_names,
                },
            }
        )
        if tokens > 0:
            token_holds.append(
                {
                    "name": name,
                    "hold": tokens,
                    "cap": token_cap,
                    "event": "status",
                }
            )

    summary = {
        "total_players": len(players_out),
        "total_checked": sum(p["checked"] for p in players_out),
        "total_stars": sum(p["stars"] for p in players_out),
    }

    publish_dir = Path(os.getenv("MRC_PUBLISH_DIR") or (storage_dir / "publish"))
    publish_dir.mkdir(parents=True, exist_ok=True)
    out_path = publish_dir / "progress.json"
    out_path.write_text(
        json.dumps(
            {
                "version": 1,
                "seed": seed,
                "generated_at": now.isoformat(),
                "summary": summary,
                "attack_logs": attack_logs[-50:],
                "token_holds": token_holds,
                "latest_logs": latest_logs[-50:],
                "players": players_out,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    state = _load_state(state_path)
    state["last_publish"] = now.isoformat()
    _save_state(state_path, state)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run preprocess/publish jobs.")
    parser.add_argument("job", choices=["preprocess", "publish"])
    args = parser.parse_args()

    tz_name = os.getenv("MRC_JOB_TIMEZONE", "Asia/Seoul")
    tz = ZoneInfo(tz_name)
    storage_dir = Path(os.getenv("MRC_SUBMIT_STORAGE_DIR", "./storage")).resolve()
    Storage(storage_dir).init()
    seed = os.getenv("MRC_SEED", "2025W")

    preprocess_at = _parse_time(os.getenv("MRC_JOB_PREPROCESS_AT", "01:00"), dt_time(1, 0))
    if args.job == "preprocess":
        path = run_preprocess(storage_dir=storage_dir, tz=tz, cutoff=preprocess_at)
        print(f"Preprocess saved: {path}")
        return
    path = run_publish(storage_dir=storage_dir, tz=tz, seed=seed)
    print(f"Publish saved: {path}")


if __name__ == "__main__":
    main()
