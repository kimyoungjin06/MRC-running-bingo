from __future__ import annotations

import json
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

from .cards import CARDS


GAME_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS seasons (
  id TEXT PRIMARY KEY,
  name TEXT,
  seed TEXT,
  start_date TEXT,
  end_date TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS players (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  tier TEXT,
  email TEXT,
  created_at TEXT,
  active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS card_sets (
  id TEXT PRIMARY KEY,
  season_id TEXT,
  name TEXT,
  version TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS cards (
  card_set_id TEXT NOT NULL,
  code TEXT NOT NULL,
  card_type TEXT NOT NULL,
  stars INTEGER NOT NULL,
  title TEXT,
  rules_json TEXT,
  meta_json TEXT,
  PRIMARY KEY (card_set_id, code)
);

CREATE TABLE IF NOT EXISTS boards (
  id TEXT PRIMARY KEY,
  season_id TEXT,
  player_id TEXT,
  card_set_id TEXT,
  created_at TEXT,
  status TEXT,
  source TEXT
);

CREATE TABLE IF NOT EXISTS board_cells (
  board_id TEXT NOT NULL,
  row INTEGER NOT NULL,
  col INTEGER NOT NULL,
  card_code TEXT,
  card_type TEXT,
  stars INTEGER,
  title TEXT,
  PRIMARY KEY (board_id, row, col),
  UNIQUE (board_id, card_code)
);

CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  season_id TEXT,
  player_id TEXT,
  run_date TEXT,
  start_time TEXT,
  distance_km REAL,
  duration_min INTEGER,
  temperature_c REAL,
  feels_like_c REAL,
  wind_m_s REAL,
  precipitation TEXT,
  is_track INTEGER,
  is_treadmill INTEGER,
  elevation_gain_m INTEGER,
  hill_repeats INTEGER,
  has_light_gear INTEGER,
  is_silent INTEGER,
  did_warmup INTEGER,
  did_cooldown INTEGER,
  did_foam_roll INTEGER,
  did_strength INTEGER,
  did_drills INTEGER,
  did_log INTEGER,
  is_new_route INTEGER,
  is_build_up INTEGER,
  is_group INTEGER,
  group_size INTEGER,
  group_tiers_json TEXT,
  day_runners_count INTEGER,
  is_thursday_meeting INTEGER,
  is_bungae INTEGER,
  is_host INTEGER,
  after_social INTEGER,
  is_easy INTEGER,
  extra_json TEXT,
  created_at TEXT,
  submission_id TEXT
);

CREATE TABLE IF NOT EXISTS claims (
  id TEXT PRIMARY KEY,
  submission_id TEXT,
  run_id TEXT,
  season_id TEXT,
  player_id TEXT,
  board_id TEXT,
  card_code TEXT,
  card_type TEXT,
  stars INTEGER,
  status TEXT,
  auto_status TEXT,
  reasons_json TEXT,
  created_at TEXT,
  decided_at TEXT,
  decided_by TEXT,
  UNIQUE (run_id, card_code)
);

CREATE TABLE IF NOT EXISTS token_events (
  id TEXT PRIMARY KEY,
  season_id TEXT,
  actor_player_id TEXT,
  event_type TEXT,
  target_player_id TEXT,
  seal_type TEXT,
  run_id TEXT,
  submission_id TEXT,
  notes TEXT,
  created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_player_date ON runs (player_id, run_date);
CREATE INDEX IF NOT EXISTS idx_claims_player_card ON claims (player_id, card_code);
CREATE INDEX IF NOT EXISTS idx_claims_status ON claims (status);
CREATE INDEX IF NOT EXISTS idx_token_events_actor ON token_events (actor_player_id);
"""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(filename: str) -> str:
    name = filename.strip().replace("\\", "_").replace("/", "_")
    name = re.sub(r"[^a-zA-Z0-9._()-]+", "_", name)
    return name[:180] or "upload"


def new_submission_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    tail = secrets.token_hex(3)
    return f"{stamp}-{tail}"


@dataclass(frozen=True)
class StoredFile:
    filename: str
    stored_as: str
    size_bytes: int


class Storage:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.submissions_dir = self.base_dir / "submissions"
        self.db_path = self.base_dir / "index.sqlite"

    def init(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.submissions_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        con = sqlite3.connect(self.db_path)
        try:
            con.executescript(GAME_SCHEMA_SQL)
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS submissions (
                  id TEXT PRIMARY KEY,
                  created_at TEXT NOT NULL,
                  player_name TEXT NOT NULL,
                  tier TEXT NOT NULL,
                  run_date TEXT,
                  start_time TEXT,
                  distance_km REAL,
                  duration_min INTEGER,
                  claimed_labels_json TEXT NOT NULL,
                  resolved_codes_json TEXT NOT NULL,
                  validation_json TEXT NOT NULL,
                  notes TEXT,
                  token_event TEXT,
                  token_hold INTEGER,
                  seal_target TEXT,
                  seal_type TEXT,
                  log_summary TEXT,
                  review_status TEXT DEFAULT 'pending',
                  reviewed_at TEXT,
                  reviewed_by TEXT,
                  review_notes TEXT,
                  review_cards_json TEXT,
                  files_json TEXT NOT NULL,
                  user_agent TEXT,
                  client_ip TEXT
                )
                """
            )
            self._ensure_columns(
                con,
                {
                    "token_event": "TEXT",
                    "token_hold": "INTEGER",
                    "seal_target": "TEXT",
                    "seal_type": "TEXT",
                    "log_summary": "TEXT",
                    "review_status": "TEXT",
                    "reviewed_at": "TEXT",
                    "reviewed_by": "TEXT",
                    "review_notes": "TEXT",
                    "review_cards_json": "TEXT",
                },
            )
            con.commit()
        finally:
            con.close()

    def _ensure_columns(self, con: sqlite3.Connection, columns: dict[str, str]) -> None:
        existing = {row[1] for row in con.execute("PRAGMA table_info(submissions)")}
        for name, col_type in columns.items():
            if name in existing:
                continue
            con.execute(f"ALTER TABLE submissions ADD COLUMN {name} {col_type}")

    def create_submission_dir(self, submission_id: str) -> Path:
        submission_dir = self.submissions_dir / submission_id
        (submission_dir / "files").mkdir(parents=True, exist_ok=False)
        return submission_dir

    def save_file(self, submission_dir: Path, upload_filename: str, content: bytes) -> StoredFile:
        safe = _safe_name(upload_filename)
        out_path = submission_dir / "files" / safe
        if out_path.exists():
            out_path = submission_dir / "files" / f"{secrets.token_hex(2)}_{safe}"
        out_path.write_bytes(content)
        return StoredFile(filename=upload_filename, stored_as=str(out_path.relative_to(submission_dir)), size_bytes=len(content))

    def write_meta(self, submission_dir: Path, meta: dict) -> None:
        (submission_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    def insert_index(
        self,
        *,
        submission_id: str,
        created_at: str,
        player_name: str,
        tier: str,
        run_date: str | None,
        start_time: str | None,
        distance_km: float | None,
        duration_min: int | None,
        claimed_labels: list[str],
        resolved_codes: list[str],
        validation: dict,
        notes: str | None,
        token_event: str | None,
        token_hold: int | None,
        seal_target: str | None,
        seal_type: str | None,
        log_summary: str | None,
        review_status: str | None = "pending",
        reviewed_at: str | None = None,
        reviewed_by: str | None = None,
        review_notes: str | None = None,
        review_cards: dict[str, str] | None = None,
        files: list[StoredFile],
        user_agent: str | None,
        client_ip: str | None,
    ) -> None:
        con = sqlite3.connect(self.db_path)
        try:
            con.execute(
                """
                INSERT INTO submissions (
                  id, created_at, player_name, tier, run_date, start_time, distance_km, duration_min,
                  claimed_labels_json, resolved_codes_json, validation_json, notes,
                  token_event, token_hold, seal_target, seal_type, log_summary,
                  review_status, reviewed_at, reviewed_by, review_notes, review_cards_json,
                  files_json, user_agent, client_ip
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    submission_id,
                    created_at,
                    player_name,
                    tier,
                    run_date,
                    start_time,
                    distance_km,
                    duration_min,
                    json.dumps(claimed_labels, ensure_ascii=False),
                    json.dumps(resolved_codes, ensure_ascii=False),
                    json.dumps(validation, ensure_ascii=False),
                    notes,
                    token_event,
                    token_hold,
                    seal_target,
                    seal_type,
                    log_summary,
                    review_status,
                    reviewed_at,
                    reviewed_by,
                    review_notes,
                    json.dumps(review_cards or {}, ensure_ascii=False),
                    json.dumps([f.__dict__ for f in files], ensure_ascii=False),
                    user_agent,
                    client_ip,
                ),
            )
            con.commit()
        finally:
            con.close()

    def list_submissions(self, *, status: str | None = None, limit: int = 200) -> list[dict]:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        try:
            clauses = []
            params: list[object] = []
            if status:
                if status == "pending":
                    clauses.append("(review_status IS NULL OR review_status = 'pending')")
                else:
                    clauses.append("review_status = ?")
                    params.append(status)
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            query = f"""
                SELECT
                  id, created_at, player_name, tier, run_date, start_time,
                  distance_km, duration_min,
                  claimed_labels_json, resolved_codes_json, validation_json, notes,
                  token_event, token_hold, seal_target, seal_type, log_summary,
                  review_status, reviewed_at, reviewed_by, review_notes, review_cards_json,
                  files_json
                FROM submissions
                {where}
                ORDER BY created_at DESC
                LIMIT ?
            """
            params.append(limit)
            rows = con.execute(query, params).fetchall()
            items = []
            for row in rows:
                try:
                    files = json.loads(row["files_json"] or "[]")
                except json.JSONDecodeError:
                    files = []
                try:
                    review_cards = json.loads(row["review_cards_json"] or "{}")
                except json.JSONDecodeError:
                    review_cards = {}
                items.append(
                    {
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
                        "token_event": row["token_event"],
                        "token_hold": row["token_hold"],
                        "seal_target": row["seal_target"],
                        "seal_type": row["seal_type"],
                        "log_summary": row["log_summary"],
                        "review_status": row["review_status"] or "pending",
                        "reviewed_at": row["reviewed_at"],
                        "reviewed_by": row["reviewed_by"],
                        "review_notes": row["review_notes"],
                        "review_cards": review_cards,
                        "files": files,
                    }
                )
            return items
        finally:
            con.close()

    def compute_token_balance(self, *, player_name: str, tier: str) -> tuple[int, int, int]:
        cap = {"beginner": 1, "intermediate": 2, "advanced": 3}.get(tier, 1)
        w_codes = {code for code, card in CARDS.items() if card.card_type == "W"}
        earned_codes: set[str] = set()
        used = 0
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute(
                """
                SELECT resolved_codes_json, review_cards_json, review_status, token_event
                FROM submissions
                WHERE player_name = ?
                ORDER BY created_at ASC
                """,
                (player_name,),
            ).fetchall()
            for row in rows:
                try:
                    codes = json.loads(row["resolved_codes_json"] or "[]")
                except json.JSONDecodeError:
                    codes = []
                try:
                    review_cards = json.loads(row["review_cards_json"] or "{}")
                except json.JSONDecodeError:
                    review_cards = {}
                if review_cards:
                    approved_codes = [code for code, status in review_cards.items() if status == "approved"]
                elif (row["review_status"] or "") == "approved":
                    approved_codes = codes
                else:
                    approved_codes = []
                earned_codes.update(code for code in approved_codes if code in w_codes)
                if (row["review_status"] or "") == "approved" and row["token_event"] in ("seal", "shield"):
                    used += 1
        finally:
            con.close()
        earned = len(earned_codes)
        available = max(0, min(cap, earned - used))
        return available, earned, used

    def get_active_seals(self, *, player_name: str, tz: ZoneInfo) -> list[dict[str, object]]:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute(
                """
                SELECT
                  created_at, player_name, run_date,
                  resolved_codes_json, token_event, seal_target, seal_type,
                  review_status
                FROM submissions
                WHERE review_status = 'approved'
                  AND (player_name = ? OR seal_target = ?)
                ORDER BY created_at ASC
                """,
                (player_name, player_name),
            ).fetchall()

            active: dict[str, dict[str, object]] = {}
            for row in rows:
                event = (row["token_event"] or "").lower()
                if event == "seal" and row["seal_target"] == player_name:
                    seal_type = (row["seal_type"] or "").upper()
                    if seal_type in ("B", "C") and seal_type not in active:
                        active[seal_type] = {
                            "type": seal_type,
                            "created_at": row["created_at"],
                            "run_days": set(),
                        }
                    continue
                if event == "shield" and row["player_name"] == player_name:
                    if active:
                        shield_type = (row["seal_type"] or "").upper()
                        if shield_type in active:
                            active.pop(shield_type, None)
                        else:
                            latest_type = max(
                                active,
                                key=lambda t: active[t].get("created_at") or "",
                            )
                            active.pop(latest_type, None)
                    continue

                if not active:
                    continue
                if row["player_name"] != player_name:
                    continue
                try:
                    codes = json.loads(row["resolved_codes_json"] or "[]")
                except json.JSONDecodeError:
                    codes = []
                if not codes:
                    continue
                run_day = row["run_date"]
                if not run_day:
                    try:
                        dt = datetime.fromisoformat(row["created_at"])
                        if dt.tzinfo:
                            dt = dt.astimezone(tz)
                        run_day = dt.date().isoformat()
                    except ValueError:
                        run_day = None
                if run_day:
                    for item in active.values():
                        item["run_days"].add(run_day)
                    expired = [key for key, item in active.items() if len(item["run_days"]) >= 2]
                    for key in expired:
                        active.pop(key, None)

            out = []
            for item in active.values():
                run_days = sorted(item["run_days"])
                remaining = max(0, 2 - len(run_days))
                out.append(
                    {
                        "type": item["type"],
                        "remaining_runs": remaining,
                        "run_days": run_days,
                    }
                )
            return out
        finally:
            con.close()

    def has_pending_or_active_seal(self, *, seal_target: str, seal_type: str) -> bool:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        try:
            row = con.execute(
                """
                SELECT 1
                FROM submissions
                WHERE token_event = 'seal'
                  AND seal_target = ?
                  AND seal_type = ?
                  AND review_status IN ('pending', 'approved')
                LIMIT 1
                """,
                (seal_target, seal_type),
            ).fetchone()
            return row is not None
        finally:
            con.close()

    def update_review_status(
        self,
        *,
        submission_id: str,
        status: str,
        reviewed_at: str,
        reviewed_by: str | None,
        review_notes: str | None,
    ) -> None:
        con = sqlite3.connect(self.db_path)
        try:
            con.execute(
                """
                UPDATE submissions
                SET review_status = ?, reviewed_at = ?, reviewed_by = ?, review_notes = ?
                WHERE id = ?
                """,
                (status, reviewed_at, reviewed_by, review_notes, submission_id),
            )
            con.commit()
        finally:
            con.close()

    def update_card_review_status(
        self,
        *,
        submission_id: str,
        card_code: str,
        status: str,
        reviewed_at: str,
        reviewed_by: str | None,
        review_notes: str | None,
    ) -> None:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        try:
            row = con.execute(
                "SELECT review_cards_json FROM submissions WHERE id = ?",
                (submission_id,),
            ).fetchone()
            if not row:
                return
            try:
                review_cards = json.loads(row["review_cards_json"] or "{}")
            except json.JSONDecodeError:
                review_cards = {}
            review_cards[card_code] = status

            values = list(review_cards.values())
            if any(v == "pending" for v in values):
                overall = "pending"
            elif any(v == "approved" for v in values):
                overall = "approved"
            else:
                overall = "rejected"

            con.execute(
                """
                UPDATE submissions
                SET review_cards_json = ?, review_status = ?, reviewed_at = ?, reviewed_by = ?, review_notes = ?
                WHERE id = ?
                """,
                (
                    json.dumps(review_cards, ensure_ascii=False),
                    overall,
                    reviewed_at,
                    reviewed_by,
                    review_notes,
                    submission_id,
                ),
            )
            con.commit()
        finally:
            con.close()

    def reject_previous_submissions(
        self,
        *,
        player_name: str,
        keep_id: str,
        run_day: str,
        reviewed_at: str,
    ) -> int:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute(
                """
                SELECT id, created_at, run_date, resolved_codes_json, review_cards_json
                FROM submissions
                WHERE player_name = ? AND id != ?
                """,
                (player_name, keep_id),
            ).fetchall()
            if not rows:
                return 0

            tz = ZoneInfo("Asia/Seoul")
            rejected = 0
            for row in rows:
                effective_day = row["run_date"]
                if not effective_day:
                    try:
                        dt = datetime.fromisoformat(row["created_at"])
                        if dt.tzinfo:
                            dt = dt.astimezone(tz)
                        effective_day = dt.date().isoformat()
                    except ValueError:
                        effective_day = None
                if effective_day != run_day:
                    continue

                try:
                    codes = json.loads(row["resolved_codes_json"] or "[]")
                except json.JSONDecodeError:
                    codes = []
                review_cards = {}
                for code in codes:
                    review_cards[code] = "rejected"

                con.execute(
                    """
                    UPDATE submissions
                    SET review_status = ?, reviewed_at = ?, reviewed_by = ?, review_notes = ?, review_cards_json = ?
                    WHERE id = ?
                    """,
                    (
                        "rejected",
                        reviewed_at,
                        "auto",
                        "자동 반려: 같은 날 최신 제출만 인정",
                        json.dumps(review_cards, ensure_ascii=False),
                        row["id"],
                    ),
                )
                rejected += 1
            con.commit()
            return rejected
        finally:
            con.close()
