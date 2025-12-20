from __future__ import annotations

import json
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


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
                  files_json, user_agent, client_ip
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    json.dumps([f.__dict__ for f in files], ensure_ascii=False),
                    user_agent,
                    client_ip,
                ),
            )
            con.commit()
        finally:
            con.close()
