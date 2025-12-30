from __future__ import annotations

import json
import os
import time
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .jobs import run_preprocess, run_publish
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


def _load_state(state_path: Path) -> dict:
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _last_run_date(state: dict, key: str, tz: ZoneInfo) -> datetime | None:
    raw = state.get(key)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).astimezone(tz)
    except ValueError:
        return None


def _job_due(now: datetime, cutoff: dt_time, last_run: datetime | None) -> bool:
    target_date = now.date()
    if now.timetz() < cutoff:
        target_date -= timedelta(days=1)
    if last_run and last_run.date() == target_date:
        return False
    return now.timetz() >= cutoff


def main() -> None:
    tz_name = os.getenv("MRC_JOB_TIMEZONE", "Asia/Seoul")
    tz = ZoneInfo(tz_name)
    storage_dir = Path(os.getenv("MRC_SUBMIT_STORAGE_DIR", "./storage")).resolve()
    state_path = storage_dir / "state.json"
    seed = os.getenv("MRC_SEED", "2025W")

    Storage(storage_dir).init()

    preprocess_at = _parse_time(os.getenv("MRC_JOB_PREPROCESS_AT", "01:00"), dt_time(1, 0))
    publish_at = _parse_time(os.getenv("MRC_JOB_PUBLISH_AT", "13:00"), dt_time(13, 0))
    sleep_sec = int(os.getenv("MRC_JOB_SLEEP_SEC", "30"))
    run_on_start = os.getenv("MRC_JOB_RUN_ON_START", "0") in ("1", "true", "yes", "on")

    if run_on_start:
        run_preprocess(storage_dir=storage_dir, tz=tz, cutoff=preprocess_at)
        run_publish(storage_dir=storage_dir, tz=tz, seed=seed)

    while True:
        now = datetime.now(tz)
        state = _load_state(state_path)
        last_pre = _last_run_date(state, "last_preprocess", tz)
        last_pub = _last_run_date(state, "last_publish", tz)

        if _job_due(now, preprocess_at, last_pre):
            run_preprocess(storage_dir=storage_dir, tz=tz, cutoff=preprocess_at)
        if _job_due(now, publish_at, last_pub):
            run_publish(storage_dir=storage_dir, tz=tz, seed=seed)

        time.sleep(sleep_sec)


if __name__ == "__main__":
    main()
