from __future__ import annotations

from datetime import date, time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .cards import CARDS, CARDS_BY_TYPE
from .config import load_settings
from .label_map import build_label_map
from .storage import Storage, new_submission_id, utc_now_iso
from .validation import RunPayload, evaluate_card, normalize_tier, validate_claim_labels


DEFAULT_SEED = "2025W"


def _parse_bool(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    return text in ("1", "true", "t", "yes", "y", "on")


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _parse_time(value: Any) -> time | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return time.fromisoformat(text)
    except ValueError:
        return None


def _client_ip(request: Request) -> str | None:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


async def _read_upload_limited(upload: UploadFile, *, max_bytes: int) -> bytes:
    data = bytearray()
    chunk_size = 1024 * 1024
    while True:
        chunk = await upload.read(chunk_size)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > max_bytes:
            raise HTTPException(status_code=413, detail=f"파일이 너무 큽니다: {upload.filename}")
    return bytes(data)


def _split_csvish(raw: list[str]) -> list[str]:
    out: list[str] = []
    for item in raw:
        if not item:
            continue
        parts = [p.strip() for p in str(item).replace("\n", ",").split(",")]
        out.extend([p for p in parts if p])
    return out


def create_app() -> FastAPI:
    base_dir = Path(__file__).resolve().parents[1]
    load_dotenv(base_dir / ".env")
    settings = load_settings(base_dir=base_dir)

    storage = Storage(settings.storage_dir)
    storage.init()

    app = FastAPI(title="MRC Binggo Submit API", version="0.1.0")
    app.state.settings = settings
    app.state.storage = storage

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/cards")
    def cards(seed: str = DEFAULT_SEED) -> dict[str, Any]:
        label_map = build_label_map(seed)
        return {
            "seed": seed,
            "cards": [
                {
                    "code": c.code,
                    "type": c.card_type,
                    "stars": c.stars,
                    "name": c.name,
                    "label": label_map.by_id.get(c.code),
                }
                for c in CARDS.values()
            ],
            "by_type": CARDS_BY_TYPE,
            "label_map": label_map.by_id,
        }

    @app.post("/api/v1/submissions")
    async def submit(request: Request, files: list[UploadFile] = File(...)) -> dict[str, Any]:
        form = await request.form()
        submit_key = (request.headers.get("x-mrc-submit-key") or form.get("submit_key") or "").strip()
        if settings.api_key and submit_key != settings.api_key:
            raise HTTPException(status_code=401, detail="제출 키가 올바르지 않습니다.")

        if not files:
            raise HTTPException(status_code=400, detail="스크린샷 파일을 1개 이상 첨부하세요.")
        if len(files) > settings.max_files:
            raise HTTPException(status_code=400, detail=f"파일은 최대 {settings.max_files}개까지 가능합니다.")

        player_name = str(form.get("player_name") or "").strip()
        if not player_name:
            raise HTTPException(status_code=400, detail="이름(player_name)을 입력하세요.")

        try:
            tier = normalize_tier(str(form.get("tier") or ""))
        except ValueError:
            raise HTTPException(status_code=400, detail="티어(tier)가 올바르지 않습니다. beginner/intermediate/advanced")

        seed = str(form.get("seed") or DEFAULT_SEED).strip() or DEFAULT_SEED

        claimed_raw = [str(v) for v in form.getlist("claimed_labels")]
        claimed_labels = _split_csvish(claimed_raw)
        rules_ok, rule_msgs = validate_claim_labels(claimed_labels)
        if not rules_ok:
            raise HTTPException(status_code=400, detail={"messages": rule_msgs})

        label_map = build_label_map(seed)
        resolved_codes: list[str] = []
        for label in [l.strip().upper() for l in claimed_labels]:
            if label not in label_map.by_label:
                raise HTTPException(status_code=400, detail=f"알 수 없는 카드 라벨: {label}")
            resolved_codes.append(label_map.by_label[label])

        group_tiers_raw = _split_csvish([str(v) for v in form.getlist("group_tiers")])
        group_tiers = tuple(normalize_tier(t.strip()) for t in group_tiers_raw if t.strip()) or None

        payload = RunPayload(
            tier=tier,
            run_date=_parse_date(form.get("run_date")),
            start_time=_parse_time(form.get("start_time")),
            distance_km=_parse_float(form.get("distance_km")),
            duration_min=_parse_int(form.get("duration_min")),
            temperature_c=_parse_float(form.get("temperature_c")),
            feels_like_c=_parse_float(form.get("feels_like_c")),
            wind_m_s=_parse_float(form.get("wind_m_s")),
            precipitation=(str(form.get("precipitation") or "none").strip().lower() or "none"),
            is_track=_parse_bool(form.get("is_track")),
            is_treadmill=_parse_bool(form.get("is_treadmill")),
            elevation_gain_m=_parse_int(form.get("elevation_gain_m")),
            hill_repeats=_parse_int(form.get("hill_repeats")),
            has_light_gear=_parse_bool(form.get("has_light_gear")),
            is_silent=_parse_bool(form.get("is_silent")),
            did_warmup=_parse_bool(form.get("did_warmup")),
            did_cooldown=_parse_bool(form.get("did_cooldown")),
            did_foam_roll=_parse_bool(form.get("did_foam_roll")),
            did_strength=_parse_bool(form.get("did_strength")),
            did_drills=_parse_bool(form.get("did_drills")),
            did_log=_parse_bool(form.get("did_log")),
            is_new_route=_parse_bool(form.get("is_new_route")),
            is_build_up=_parse_bool(form.get("is_build_up")),
            is_group=_parse_bool(form.get("is_group")),
            group_size=_parse_int(form.get("group_size")),
            group_tiers=group_tiers,
            day_runners_count=_parse_int(form.get("day_runners_count")),
            is_thursday_meeting=_parse_bool(form.get("is_thursday_meeting")),
            is_bungae=_parse_bool(form.get("is_bungae")),
            is_host=_parse_bool(form.get("is_host")),
            after_social=_parse_bool(form.get("after_social")),
            is_easy=_parse_bool(form.get("is_easy")),
        )

        validations: list[dict[str, Any]] = []
        for label, code in zip(claimed_labels, resolved_codes, strict=False):
            status, reasons = evaluate_card(code, payload)
            card = CARDS.get(code)
            validations.append(
                {
                    "label": label.strip().upper(),
                    "resolved_code": code,
                    "type": card.card_type if card else None,
                    "stars": card.stars if card else None,
                    "status": status,
                    "reasons": reasons,
                }
            )

        submission_id = new_submission_id()
        submission_dir = storage.create_submission_dir(submission_id)

        stored_files = []
        for upload in files:
            content = await _read_upload_limited(upload, max_bytes=settings.max_file_bytes)
            stored_files.append(storage.save_file(submission_dir, upload.filename or "upload", content))

        created_at = utc_now_iso()
        notes = str(form.get("notes") or "").strip() or None
        token_event = (str(form.get("token_event") or "").strip().lower() or None)
        if token_event not in (None, "earned", "seal", "shield"):
            raise HTTPException(status_code=400, detail="token_event 값이 올바르지 않습니다.")
        token_hold = _parse_int(form.get("token_hold"))
        if token_hold not in (None, 0, 1):
            raise HTTPException(status_code=400, detail="token_hold 값이 올바르지 않습니다.")
        seal_target = str(form.get("seal_target") or "").strip() or None
        seal_type = (str(form.get("seal_type") or "").strip().upper() or None)
        if seal_type and seal_type not in ("B", "C"):
            raise HTTPException(status_code=400, detail="seal_type 값이 올바르지 않습니다.")
        log_summary = str(form.get("log_summary") or "").strip() or None

        meta = {
            "id": submission_id,
            "created_at": created_at,
            "seed": seed,
            "player_name": player_name,
            "tier": tier,
            "run": {
                "run_date": payload.run_date.isoformat() if payload.run_date else None,
                "start_time": payload.start_time.isoformat(timespec="minutes") if payload.start_time else None,
                "distance_km": payload.distance_km,
                "duration_min": payload.duration_min,
                "temperature_c": payload.temperature_c,
                "feels_like_c": payload.feels_like_c,
                "wind_m_s": payload.wind_m_s,
                "precipitation": payload.precipitation,
            },
            "claimed_labels": [l.strip().upper() for l in claimed_labels],
            "resolved_codes": resolved_codes,
            "validation": validations,
            "notes": notes,
            "token": {
                "event": token_event,
                "hold": token_hold,
                "seal_target": seal_target,
                "seal_type": seal_type,
                "log_summary": log_summary,
            },
            "files": [f.__dict__ for f in stored_files],
            "client": {
                "user_agent": request.headers.get("user-agent"),
                "ip": _client_ip(request),
            },
        }

        storage.write_meta(submission_dir, meta)
        storage.insert_index(
            submission_id=submission_id,
            created_at=created_at,
            player_name=player_name,
            tier=tier,
            run_date=payload.run_date.isoformat() if payload.run_date else None,
            start_time=payload.start_time.isoformat(timespec="minutes") if payload.start_time else None,
            distance_km=payload.distance_km,
            duration_min=payload.duration_min,
            claimed_labels=[l.strip().upper() for l in claimed_labels],
            resolved_codes=resolved_codes,
            validation={"cards": validations},
            notes=notes,
            token_event=token_event,
            token_hold=token_hold,
            seal_target=seal_target,
            seal_type=seal_type,
            log_summary=log_summary,
            files=stored_files,
            user_agent=request.headers.get("user-agent"),
            client_ip=_client_ip(request),
        )

        summary = {
            "passed": sum(1 for v in validations if v["status"] == "passed"),
            "failed": sum(1 for v in validations if v["status"] == "failed"),
            "needs_review": sum(1 for v in validations if v["status"] == "needs_review"),
        }

        return {
            "id": submission_id,
            "created_at": created_at,
            "player_name": player_name,
            "tier": tier,
            "seed": seed,
            "claimed_labels": [l.strip().upper() for l in claimed_labels],
            "resolved_codes": resolved_codes,
            "rule_messages": rule_msgs,
            "validation": validations,
            "summary": summary,
            "stored_files": [f.__dict__ for f in stored_files],
        }

    return app
