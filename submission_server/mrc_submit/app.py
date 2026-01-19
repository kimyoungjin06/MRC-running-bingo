from __future__ import annotations

from datetime import date, datetime, time, timedelta
import html
import json
import mimetypes
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

from .boards import generate_boards_from_xlsx, load_boards_json, parse_carddeck, write_boards_json
from .cards import CARDS, CARDS_BY_TYPE
from .config import load_settings
from .jobs import run_publish
from .label_map import build_label_map
from .storage import Storage, new_submission_id, utc_now_iso
from .validation import RunPayload, evaluate_card, normalize_claim_labels, normalize_tier, tier_value, validate_claim_labels


DEFAULT_SEED = "2025W"
ADMIN_COOKIE_NAME = "mrc_admin"


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


def _load_board_codes(storage_dir: Path, *, carddeck_path: Path, seed: str, map_labels: bool) -> dict[str, set[str]]:
    env_path = os.getenv("MRC_BOARDS_PATH")
    boards_path = Path(env_path) if env_path else storage_dir / "boards" / "boards.json"
    data = load_boards_json(
        boards_path,
        carddeck_path=carddeck_path,
        label_seed=seed,
        apply_label_map=map_labels,
    )
    if not data:
        return {}
    result: dict[str, set[str]] = {}
    for board in data.get("boards", []) if isinstance(data, dict) else []:
        name = (board or {}).get("name")
        if not name:
            continue
        grid = (board or {}).get("grid", [])
        codes = {
            cell.get("code")
            for row in grid
            for cell in (row or [])
            if isinstance(cell, dict) and cell.get("code")
        }
        if codes:
            result[name] = codes
    return result


def _normalize_tier_label(value: str) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    lowered = raw.lower()
    if lowered in ("beginner", "intermediate", "advanced"):
        return lowered
    mapping = {"초보": "beginner", "중수": "intermediate", "고수": "advanced"}
    return mapping.get(raw)


def _load_tier_from_boards(storage_dir: Path, player_name: str) -> str | None:
    env_path = os.getenv("MRC_BOARDS_PATH")
    boards_path = Path(env_path) if env_path else storage_dir / "boards" / "boards.json"
    if not boards_path.exists():
        return None
    try:
        data = json.loads(boards_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    for board in data.get("boards", []) if isinstance(data, dict) else []:
        if (board or {}).get("name") != player_name:
            continue
        tier = _normalize_tier_label((board or {}).get("tier") or (board or {}).get("tier_label") or "")
        if tier:
            return tier
    return None


def _admin_key_from(request: Request, form: dict | None = None) -> str:
    if "x-mrc-admin-key" in request.headers:
        return request.headers.get("x-mrc-admin-key") or ""
    if form:
        return str(form.get("admin_key") or "")
    cookie = request.cookies.get(ADMIN_COOKIE_NAME)
    if cookie:
        return cookie
    return ""


def _require_admin(settings, request: Request, form: dict | None = None) -> str:
    key = _admin_key_from(request, form)
    if settings.admin_key and key != settings.admin_key:
        raise HTTPException(status_code=401, detail="admin key required")
    return key


def _is_secure_request(request: Request) -> bool:
    if request.url.scheme == "https":
        return True
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto:
        return forwarded_proto.split(",")[0].strip().lower() == "https"
    return False


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


def _validation_summary(validation: dict | list) -> str:
    if isinstance(validation, dict):
        cards = validation.get("cards")
    else:
        cards = validation
    if not cards:
        return "-"
    passed = sum(1 for v in cards if v.get("status") == "passed")
    failed = sum(1 for v in cards if v.get("status") == "failed")
    needs = sum(1 for v in cards if v.get("status") == "needs_review")
    return f"통과 {passed} / 실패 {failed} / 확인 {needs}"


def _load_card_titles(carddeck_path: Path) -> dict[str, str]:
    try:
        cards = parse_carddeck(carddeck_path)
    except (FileNotFoundError, OSError, ValueError):
        return {}
    return {code: card.title for code, card in cards.items()}


def _format_card_list(
    validation: dict | list,
    card_titles: dict[str, str],
    *,
    fallback_codes: list[str] | None = None,
    review_cards: dict[str, str] | None = None,
) -> str:
    cards = validation.get("cards") if isinstance(validation, dict) else validation
    if not cards:
        if not fallback_codes:
            return "-"
        items = []
        for code in fallback_codes:
            title = card_titles.get(code, "")
            title_html = f' <span class="card-title">{html.escape(title)}</span>' if title else ""
            review_status = (review_cards or {}).get(code)
            review_html = (
                f' <span class="card-status card-status--review-{html.escape(review_status)}">{html.escape(_card_review_label(review_status))}</span>'
                if review_status
                else ""
            )
            items.append(f"<li><span class=\"card-code\">{html.escape(code)}</span>{title_html}{review_html}</li>")
        return f"<ul class=\"card-list\">{''.join(items)}</ul>"

    items = []
    for item in cards:
        label = item.get("label") or item.get("resolved_code") or "-"
        resolved = item.get("resolved_code") or item.get("label") or ""
        title = card_titles.get(resolved) or card_titles.get(label) or ""
        status = item.get("status")
        status_text = _card_status_label(status)
        review_status = (review_cards or {}).get(resolved) or (review_cards or {}).get(label)
        review_html = (
            f' <span class="card-status card-status--review-{html.escape(review_status)}">{html.escape(_card_review_label(review_status))}</span>'
            if review_status
            else ""
        )
        status_html = (
            f' <span class="card-status card-status--{html.escape(status)}">{html.escape(status_text)}</span>'
            if status
            else ""
        )
        title_html = f' <span class="card-title">{html.escape(title)}</span>' if title else ""
        items.append(
            f"<li><span class=\"card-code\">{html.escape(label)}</span>{title_html}{status_html}{review_html}</li>"
        )
    return f"<ul class=\"card-list\">{''.join(items)}</ul>"


def _load_submission_meta(storage: Storage, submission_id: str) -> dict[str, Any] | None:
    meta_path = storage.submissions_dir / submission_id / "meta.json"
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _week_bounds(value: date) -> tuple[date, date]:
    start = value - timedelta(days=value.weekday())
    end = start + timedelta(days=6)
    return start, end


def _tier_label(tier: str | None) -> str:
    if tier == "beginner":
        return "초보"
    if tier == "intermediate":
        return "중수"
    if tier == "advanced":
        return "고수"
    return tier or "-"


def _unique_preserve(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _run_publish_now(storage_dir: Path) -> tuple[bool, str]:
    try:
        tz_name = os.getenv("MRC_JOB_TIMEZONE", "Asia/Seoul")
        tz = ZoneInfo(tz_name)
        seed = os.getenv("MRC_SEED", DEFAULT_SEED)
        run_publish(storage_dir=storage_dir, tz=tz, seed=seed)
        return True, "업데이트 반영 완료"
    except Exception:
        return False, "업데이트 반영 실패"


def _status_label(value: str | None) -> str:
    mapping = {
        "pending": "대기",
        "approved": "승인",
        "rejected": "반려",
        "all": "전체",
    }
    if not value:
        return "-"
    return mapping.get(value.lower(), value)


def _reject_reason(item: dict[str, Any]) -> str:
    submission_status = item.get("review_status") or "pending"
    if submission_status != "rejected":
        return ""
    review_notes = item.get("review_notes") or ""
    reviewed_by = (item.get("reviewed_by") or "").strip()
    if reviewed_by == "auto" and "같은 날 최신 제출만 인정" in review_notes:
        return "자동 반려(중복 제출)"
    if reviewed_by == "auto":
        return "자동 반려"
    return "운영진 반려"


def _card_status_label(value: str | None) -> str:
    mapping = {
        "passed": "통과",
        "failed": "실패",
        "needs_review": "확인 필요",
    }
    if not value:
        return "-"
    return mapping.get(value, value)


def _card_review_label(value: str | None) -> str:
    mapping = {
        "approved": "승인",
        "rejected": "반려",
        "pending": "대기",
    }
    if not value:
        return "-"
    return mapping.get(value, value)


def _format_created_at(value: str | None) -> str:
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(value)
        tz_name = os.getenv("MRC_JOB_TIMEZONE", "Asia/Seoul")
        tz = ZoneInfo(tz_name)
        if dt.tzinfo:
            dt = dt.astimezone(tz)
        return dt.replace(microsecond=0).isoformat(sep=" ")
    except ValueError:
        text = value.replace("T", " ")
        if "." in text:
            text = text.split(".", 1)[0]
        return text


def _format_run_date(value: str | None) -> str:
    if not value:
        return "-"
    try:
        run_date = date.fromisoformat(value)
    except ValueError:
        return value
    weekday = "월화수목금토일"[run_date.weekday()]
    return f"{run_date.isoformat()} ({weekday})"


def _effective_run_day(run_date: date | None, created_at: str) -> str:
    if run_date:
        return run_date.isoformat()
    try:
        dt = datetime.fromisoformat(created_at)
    except ValueError:
        return ""
    tz_name = os.getenv("MRC_JOB_TIMEZONE", "Asia/Seoul")
    tz = ZoneInfo(tz_name)
    if dt.tzinfo:
        dt = dt.astimezone(tz)
    return dt.date().isoformat()


def _format_boards_meta(meta: dict | None, fallback_name: str) -> str:
    if not meta:
        return "없음"
    source = str(meta.get("source") or fallback_name)
    source_name = Path(source).name
    if source_name.startswith("upload-"):
        source_name = source_name[len("upload-") :]
    generated_at = _format_created_at(meta.get("generated_at"))
    return f"{source_name} · 생성 {generated_at}"


def _build_admin_query(
    *,
    status: str,
    run_date: str | None = None,
    runner: str | None = None,
    msg: str | None = None,
) -> str:
    params: dict[str, str] = {"status": status}
    if run_date:
        params["run_date"] = run_date
    if runner:
        params["runner"] = runner
    if msg:
        params["msg"] = msg
    return urlencode(params)


def _build_filter_options(items: list[dict]) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    date_counts: dict[str, int] = {}
    runner_counts: dict[str, int] = {}
    for item in items:
        run_date = item.get("run_date")
        if run_date:
            date_counts[run_date] = date_counts.get(run_date, 0) + 1
        name = item.get("player_name")
        if name:
            runner_counts[name] = runner_counts.get(name, 0) + 1
    date_options = sorted(date_counts.items(), key=lambda x: x[0], reverse=True)
    runner_options = sorted(runner_counts.items(), key=lambda x: (-x[1], x[0]))
    return date_options, runner_options


def _build_submission_indexes(items: list[dict]) -> tuple[dict[date, list[str]], dict[str, list[date]]]:
    by_date: dict[date, list[str]] = {}
    by_player: dict[str, list[date]] = {}
    for item in items:
        name = item.get("player_name")
        run_date = _parse_iso_date(item.get("run_date"))
        if not name or not run_date:
            continue
        by_date.setdefault(run_date, []).append(name)
        by_player.setdefault(name, []).append(run_date)
    for key, names in list(by_date.items()):
        by_date[key] = _unique_preserve(names)
    for key, dates in list(by_player.items()):
        by_player[key] = sorted(set(dates))
    return by_date, by_player


def _build_insights(item: dict, *, by_date: dict[date, list[str]], by_player: dict[str, list[date]]) -> str:
    codes = item.get("resolved_codes") or []
    if not codes:
        return "-"

    run_date = _parse_iso_date(item.get("run_date"))
    name = item.get("player_name") or "-"
    tier = item.get("tier") or "-"
    distance_km = item.get("distance_km")
    duration_min = item.get("duration_min")
    insights: list[str] = []

    for code in codes:
        if code == "A01":
            threshold = tier_value(tier, 5.0, 7.0, 10.0)
            value = f"{distance_km}km" if distance_km is not None else "거리 입력 필요"
            insights.append(f"A01 기준: {_tier_label(tier)} {threshold}km, 제출 {value}")
        elif code == "A02":
            threshold = tier_value(tier, 6.0, 8.0, 12.0)
            value = f"{distance_km}km" if distance_km is not None else "거리 입력 필요"
            insights.append(f"A02 기준: {_tier_label(tier)} {threshold}km, 제출 {value}")
        elif code == "A03":
            threshold = tier_value(tier, 7.0, 10.0, 15.0)
            value = f"{distance_km}km" if distance_km is not None else "거리 입력 필요"
            insights.append(f"A03 기준: {_tier_label(tier)} {threshold}km, 제출 {value}")
        elif code == "A04":
            threshold = tier_value(tier, 30.0, 40.0, 50.0)
            value = f"{duration_min}분" if duration_min is not None else "시간 입력 필요"
            insights.append(f"A04 기준: {_tier_label(tier)} {threshold}분, 제출 {value}")
        elif code == "A05":
            threshold = tier_value(tier, 50.0, 60.0, 70.0)
            value = f"{duration_min}분" if duration_min is not None else "시간 입력 필요"
            insights.append(f"A05 기준: {_tier_label(tier)} {threshold}분, 제출 {value}")
        elif code == "B01":
            start_time = item.get("start_time") or "시간 입력 필요"
            insights.append(f"B01 시작 시간: {start_time}")
        elif code == "B02":
            start_time = item.get("start_time") or "시간 입력 필요"
            insights.append(f"B02 시작 시간: {start_time}")
        elif code == "B05":
            if run_date:
                weekday = "월화수목금토일"[run_date.weekday()]
                insights.append(f"B05 날짜: {run_date.isoformat()} ({weekday})")
            else:
                insights.append("B05 날짜 입력 필요")
        elif code == "C04":
            if run_date:
                names = by_date.get(run_date, [])
                names_text = ", ".join(names) if names else "-"
                insights.append(f"C04 당일 인증 {len(names)}명: {names_text}")
            else:
                insights.append("C04 날짜 입력 필요")
        elif code == "D02":
            if run_date:
                start, end = _week_bounds(run_date)
                dates = [d for d in by_player.get(name, []) if start <= d <= end]
                dates_text = ", ".join(d.isoformat() for d in dates) if dates else "-"
                insights.append(
                    f"D02 주간({start.isoformat()}~{end.isoformat()}): {len(dates)}회 ({dates_text})"
                )
            else:
                insights.append("D02 날짜 입력 필요")

    if not insights:
        return "-"
    items_html = "".join(f"<li>{html.escape(text)}</li>" for text in insights)
    return f"<ul class=\"insights\">{items_html}</ul>"


def _render_admin_page(
    *,
    items: list[dict],
    index_items: list[dict],
    status: str,
    message: str,
    boards_meta: str,
    card_titles: dict[str, str],
    run_date_filter: str | None,
    runner_filter: str | None,
    admin_key: str,
) -> str:
    by_date, by_player = _build_submission_indexes(index_items)
    date_options, runner_options = _build_filter_options(index_items)
    submitters = _unique_preserve([item.get("player_name") for item in items if item.get("player_name")])
    if submitters:
        submitters_html = f"{len(submitters)}명 · " + ", ".join(html.escape(name) for name in submitters)
    else:
        submitters_html = "-"
    filter_query = _build_admin_query(
        status=status,
        run_date=run_date_filter,
        runner=runner_filter,
    )
    filter_summary_parts = []
    if runner_filter:
        filter_summary_parts.append(f"러너: {html.escape(runner_filter)}")
    if run_date_filter:
        filter_summary_parts.append(f"날짜: {_format_run_date(run_date_filter)}")
    filter_summary = " · ".join(filter_summary_parts) if filter_summary_parts else "없음"

    runner_select_options = ['<option value="">전체</option>']
    for name, count in runner_options:
        selected = " selected" if runner_filter == name else ""
        escaped = html.escape(name)
        runner_select_options.append(f"<option value=\"{escaped}\"{selected}>{escaped} ({count})</option>")
    runner_select_html = "\n".join(runner_select_options)

    date_select_options = ['<option value="">전체</option>']
    for run_date, count in date_options:
        selected = " selected" if run_date_filter == run_date else ""
        label = _format_run_date(run_date)
        date_select_options.append(
            f"<option value=\"{html.escape(run_date)}\"{selected}>{html.escape(label)} ({count})</option>"
        )
    date_select_html = "\n".join(date_select_options)

    date_links = []
    for run_date, count in date_options:
        link_query = _build_admin_query(status=status, run_date=run_date, runner=runner_filter)
        label = _format_run_date(run_date)
        active = " is-active" if run_date_filter == run_date else ""
        date_links.append(
            f"<a class=\"filter-chip{active}\" href=\"/admin?{link_query}#submissions\">{html.escape(label)} ({count})</a>"
        )
    date_links_html = " ".join(date_links) if date_links else "-"

    runner_links = []
    for name, count in runner_options:
        link_query = _build_admin_query(status=status, run_date=run_date_filter, runner=name)
        active = " is-active" if runner_filter == name else ""
        runner_links.append(
            f"<a class=\"filter-chip{active}\" href=\"/admin?{link_query}#submissions\">{html.escape(name)} ({count})</a>"
        )
    runner_links_html = " ".join(runner_links) if runner_links else "-"
    rows = []
    for item in items:
        created = _format_created_at(item.get("created_at"))
        name = item.get("player_name") or "-"
        tier = _tier_label(item.get("tier"))
        run_date = _format_run_date(item.get("run_date"))
        summary = _validation_summary(item.get("validation") or {})
        review_notes = item.get("review_notes") or ""
        review_cards = item.get("review_cards") or {}
        submission_status = item.get("review_status") or "pending"
        reject_reason = _reject_reason(item)
        cards_html = _format_card_list(
            item.get("validation") or {},
            card_titles,
            fallback_codes=item.get("resolved_codes") or [],
            review_cards=review_cards,
        )
        files = item.get("files") or []
        file_count = len(files)
        if file_count:
            file_link = f"/admin/submissions/{item['id']}"
            files_html = f"<a class=\"btn-link\" href=\"{file_link}\">사진 보기 ({file_count})</a>"
        else:
            files_html = "-"
        insights_html = _build_insights(item, by_date=by_date, by_player=by_player)
        action_parts = []
        validation_cards = (item.get("validation") or {}).get("cards") if isinstance(item.get("validation"), dict) else None
        if validation_cards:
            for card in validation_cards:
                code = card.get("resolved_code") or card.get("label") or "-"
                label = card.get("label") or code
                status = review_cards.get(code) or review_cards.get(label)
                if not status:
                    if not review_cards and submission_status in ("approved", "rejected"):
                        status = submission_status
                    else:
                        status = "pending"
                status_label = _card_review_label(status)
                status_html = (
                    f'<span class="card-status card-status--review-{html.escape(status)}">{html.escape(status_label)}</span>'
                )
                if status == "pending":
                    form_html = f"""
                      <form method="post" action="/admin/review/{item['id']}?{filter_query}">
                        <input type="hidden" name="admin_key" value="{html.escape(admin_key)}" />
                        <input type="hidden" name="card_code" value="{html.escape(code)}" />
                        <button type="submit" name="review_status" value="approved">승인</button>
                        <button type="submit" name="review_status" value="rejected">반려</button>
                      </form>
                    """
                else:
                    form_html = ""
                action_parts.append(
                    f'<div><span class="card-code">{html.escape(label)}</span> {status_html}{form_html}</div>'
                )
        else:
            for code in item.get("resolved_codes") or []:
                status = review_cards.get(code)
                if not status:
                    if not review_cards and submission_status in ("approved", "rejected"):
                        status = submission_status
                    else:
                        status = "pending"
                status_label = _card_review_label(status)
                status_html = (
                    f'<span class="card-status card-status--review-{html.escape(status)}">{html.escape(status_label)}</span>'
                )
                if status == "pending":
                    form_html = f"""
                      <form method="post" action="/admin/review/{item['id']}?{filter_query}">
                        <input type="hidden" name="admin_key" value="{html.escape(admin_key)}" />
                        <input type="hidden" name="card_code" value="{html.escape(code)}" />
                        <button type="submit" name="review_status" value="approved">승인</button>
                        <button type="submit" name="review_status" value="rejected">반려</button>
                      </form>
                    """
                else:
                    form_html = ""
                action_parts.append(
                    f'<div><span class="card-code">{html.escape(code)}</span> {status_html}{form_html}</div>'
                )
        if not action_parts and submission_status == "pending":
            action_parts.append(
                f"""
                <form method="post" action="/admin/review/{item['id']}?{filter_query}">
                  <input type="hidden" name="admin_key" value="{html.escape(admin_key)}" />
                  <button type="submit" name="review_status" value="approved">승인</button>
                  <button type="submit" name="review_status" value="rejected">반려</button>
                </form>
                """
            )
        if reject_reason:
            action_parts.insert(0, f'<div class="review-badge review-badge--rejected">{html.escape(reject_reason)}</div>')
        action_html = "\n".join(action_parts) if action_parts else "-"
        row = f"""
          <tr>
            <td>{created}</td>
            <td>{name}</td>
            <td>{tier}</td>
            <td>{run_date}</td>
            <td>{cards_html}</td>
            <td>{summary}</td>
            <td>{insights_html}</td>
            <td>{files_html}</td>
            <td>{action_html}</td>
          </tr>
        """
        rows.append(row)

    pending_query = _build_admin_query(status="pending", run_date=run_date_filter, runner=runner_filter)
    approved_query = _build_admin_query(status="approved", run_date=run_date_filter, runner=runner_filter)
    rejected_query = _build_admin_query(status="rejected", run_date=run_date_filter, runner=runner_filter)
    all_query = _build_admin_query(status="all", run_date=run_date_filter, runner=runner_filter)

    status_label = f"{_status_label(status)} · {len(items)}건"
    table_rows = "\n".join(rows) if rows else "<tr><td colspan='9'>제출 내역 없음</td></tr>"
    return f"""
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>운영진</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #111827; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; font-size: 12px; vertical-align: top; }}
    th {{ background: #f4f4f4; text-align: left; }}
    .meta {{ display: grid; gap: 6px; margin-top: 6px; color: #374151; }}
    .message {{ color: #0a6; }}
    .hint {{ margin: 6px 0 0; font-size: 12px; color: #6b7280; }}
    .notice {{ margin-top: 8px; font-size: 12px; color: #b91c1c; }}
    .card-list {{ margin: 0; padding-left: 16px; }}
    .card-list li {{ margin-bottom: 4px; }}
    .card-code {{ font-weight: 700; }}
    .card-title {{ color: #374151; }}
    .card-status {{ font-size: 11px; padding: 1px 6px; border-radius: 999px; background: #eef2ff; margin-left: 4px; }}
    .card-status--failed {{ background: #fee2e2; }}
    .card-status--needs_review {{ background: #fef3c7; }}
    .card-status--passed {{ background: #dcfce7; }}
    .card-status--review-approved {{ background: #dcfce7; }}
    .card-status--review-rejected {{ background: #fee2e2; }}
    .card-status--review-pending {{ background: #fef3c7; }}
    .review-badge {{ display: inline-flex; align-items: center; gap: 6px; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; }}
    .review-badge--rejected {{ background: #fee2e2; color: #991b1b; }}
    .btn-link {{ display: inline-block; padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 8px; text-decoration: none; color: #111827; background: #ffffff; }}
    .insights {{ margin: 0; padding-left: 16px; color: #374151; }}
    .insights li {{ margin-bottom: 4px; }}
    .nav-bar {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 18px 0; }}
    .section-title {{ margin: 0; }}
    .page-header {{ display: flex; gap: 18px; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; }}
    .header-actions {{ min-width: 260px; padding: 12px; border: 1px solid #e5e7eb; border-radius: 12px; background: #f9fafb; }}
    .header-actions form {{ display: grid; gap: 8px; }}
    .section-row {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; margin: 12px 0; flex-wrap: wrap; }}
    .action-form button {{ padding: 8px 12px; border-radius: 8px; border: 1px solid #111827; background: #111827; color: #ffffff; }}
    .filter-panel {{ margin: 12px 0; padding: 12px; border: 1px solid #e5e7eb; border-radius: 12px; background: #f9fafb; }}
    .filter-form {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: end; }}
    .filter-form label {{ display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: #374151; }}
    .filter-form select {{ min-width: 160px; padding: 6px 8px; border: 1px solid #d1d5db; border-radius: 6px; }}
    .filter-meta {{ font-size: 12px; color: #6b7280; margin-bottom: 8px; }}
    .filter-lists {{ display: grid; gap: 6px; margin-top: 8px; font-size: 12px; color: #374151; }}
    .filter-list {{ display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }}
    .filter-label {{ font-weight: 600; margin-right: 4px; }}
    .filter-chip {{ display: inline-block; padding: 4px 8px; border-radius: 999px; border: 1px solid #d1d5db; text-decoration: none; color: #111827; background: #ffffff; }}
    .filter-chip.is-active {{ border-color: #111827; background: #111827; color: #ffffff; }}
  </style>
</head>
<body>
  <header class="page-header" id="boards">
    <div>
      <h1>운영진 관리</h1>
      <div class="meta">
        <div>빙고판: {boards_meta}</div>
        <div>제출자(현재 목록): {submitters_html}</div>
        <div class="message">{message}</div>
        <div class="notice">자동 판정은 참고용입니다. 최종 확정은 운영진 확인 후 반영됩니다.</div>
      </div>
    </div>
    <div class="header-actions">
      <h2 class="section-title">빙고판 업로드</h2>
      <p class="hint">설문 응답(.xlsx)을 업로드하면 보드가 갱신됩니다.</p>
      <form method="post" action="/admin/boards/upload" enctype="multipart/form-data">
        <input type="hidden" name="admin_key" value="{html.escape(admin_key)}" />
        <input type="file" name="file" accept=".xlsx" required />
        <button type="submit">업로드</button>
      </form>
    </div>
  </header>

  <nav class="nav-bar">
    <a class="btn-link" href="/admin?{pending_query}#submissions">대기</a>
    <a class="btn-link" href="/admin?{approved_query}#submissions">승인</a>
    <a class="btn-link" href="/admin?{rejected_query}#submissions">반려</a>
    <a class="btn-link" href="/admin?{all_query}#submissions">전체</a>
  </nav>

  <section id="submissions">
    <div class="section-row">
      <div>
        <h2 class="section-title">제출 목록 ({status_label})</h2>
        <p class="hint">자동 판정 결과와 검토 메모를 확인하세요.</p>
      </div>
      <form method="post" action="/admin/publish?{filter_query}" class="action-form">
        <input type="hidden" name="admin_key" value="{html.escape(admin_key)}" />
        <button type="submit">업데이트 반영</button>
      </form>
    </div>
    <div class="filter-panel">
      <div class="filter-meta">현재 필터: {filter_summary}</div>
      <form method="get" action="/admin" class="filter-form">
        <input type="hidden" name="status" value="{html.escape(status)}" />
        <label>
          러너
          <select name="runner">
            {runner_select_html}
          </select>
        </label>
        <label>
          날짜
          <select name="run_date">
            {date_select_html}
          </select>
        </label>
        <button type="submit">필터 적용</button>
        <a class="btn-link" href="/admin?{_build_admin_query(status=status)}#submissions">초기화</a>
      </form>
      <div class="filter-lists">
        <div class="filter-list">
          <span class="filter-label">일자별</span>
          {date_links_html}
        </div>
        <div class="filter-list">
          <span class="filter-label">러너별</span>
          {runner_links_html}
        </div>
      </div>
    </div>
    <table>
      <thead>
        <tr>
          <th>제출 시간</th>
          <th>이름</th>
          <th>티어</th>
          <th>러닝 날짜</th>
          <th>카드(라벨)</th>
          <th>자동 판정</th>
          <th>규칙 요약</th>
          <th>첨부</th>
          <th>리뷰</th>
        </tr>
      </thead>
      <tbody>
        {table_rows}
      </tbody>
    </table>
  </section>
</body>
</html>
"""


def _render_admin_submission_page(
    *,
    submission_id: str,
    meta: dict[str, Any],
    card_titles: dict[str, str],
) -> str:
    name = meta.get("player_name") or "-"
    created = _format_created_at(meta.get("created_at"))
    tier = _tier_label(meta.get("tier"))
    run = meta.get("run") or {}
    run_date = _format_run_date(run.get("run_date"))
    start_time = run.get("start_time") or "-"
    distance = run.get("distance_km")
    duration = run.get("duration_min")
    distance_text = f"{distance}km" if distance is not None else "-"
    duration_text = f"{duration}분" if duration is not None else "-"
    reject_reason = _reject_reason(meta)
    reject_html = (
        f'<div class="review-badge review-badge--rejected">{html.escape(reject_reason)}</div>'
        if reject_reason
        else ""
    )
    cards_html = _format_card_list(
        meta.get("validation") or [],
        card_titles,
        fallback_codes=meta.get("resolved_codes") or [],
    )
    files = meta.get("files") or []
    file_items = []
    for idx, info in enumerate(files):
        filename = info.get("filename") or info.get("stored_as") or f"file-{idx + 1}"
        file_url = f"/admin/submissions/{submission_id}/files/{idx}"
        escaped = html.escape(filename)
        if Path(filename).suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
            file_items.append(
                f"""
                <figure class="file-item">
                  <a href="{file_url}" target="_blank" rel="noopener">이미지 열기</a>
                  <img src="{file_url}" alt="{escaped}" loading="lazy" />
                  <figcaption>{escaped}</figcaption>
                </figure>
                """
            )
        else:
            file_items.append(
                f"<div class=\"file-item\"><a href=\"{file_url}\" target=\"_blank\" rel=\"noopener\">{escaped}</a></div>"
            )

    files_html = "".join(file_items) if file_items else "<p>첨부 파일 없음</p>"
    return f"""
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>운영진 · {html.escape(submission_id)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #111827; }}
    a {{ color: inherit; }}
    .meta {{ margin-bottom: 16px; }}
    .chips {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0 16px; }}
    .chip {{ padding: 4px 8px; border-radius: 999px; background: #f3f4f6; font-size: 12px; }}
    .card-list {{ margin: 0; padding-left: 16px; }}
    .card-list li {{ margin-bottom: 4px; }}
    .card-code {{ font-weight: 700; }}
    .card-title {{ color: #374151; }}
    .card-status {{ font-size: 11px; padding: 1px 6px; border-radius: 999px; background: #eef2ff; margin-left: 4px; }}
    .card-status--failed {{ background: #fee2e2; }}
    .card-status--needs_review {{ background: #fef3c7; }}
    .card-status--passed {{ background: #dcfce7; }}
    .review-badge {{ display: inline-flex; align-items: center; gap: 6px; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; }}
    .review-badge--rejected {{ background: #fee2e2; color: #991b1b; }}
    .files {{ display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }}
    .file-item {{ border: 1px solid #e5e7eb; border-radius: 10px; padding: 8px; background: #f9fafb; }}
    .file-item img {{ width: 100%; border-radius: 8px; margin-top: 6px; }}
    .nav-bar {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 0 0 16px; }}
    .btn-link {{ display: inline-block; padding: 4px 8px; border: 1px solid #d1d5db; border-radius: 6px; text-decoration: none; color: #111827; background: #ffffff; }}
  </style>
</head>
<body>
  <div class="nav-bar">
    <a class="btn-link" href="/admin?status=pending#submissions">대기</a>
    <a class="btn-link" href="/admin?status=approved#submissions">승인</a>
    <a class="btn-link" href="/admin?status=rejected#submissions">반려</a>
    <a class="btn-link" href="/admin?status=all#submissions">전체</a>
    <a class="btn-link" href="/admin?status=pending#boards">빙고판 업로드</a>
  </div>
  <h1>제출 상세</h1>
  <div class="meta">
    <div><strong>이름</strong>: {html.escape(str(name))}</div>
    <div><strong>제출 시간</strong>: {html.escape(str(created))}</div>
    {reject_html}
  </div>
  <div class="chips">
    <span class="chip">티어: {html.escape(str(tier))}</span>
    <span class="chip">러닝 날짜: {html.escape(str(run_date))}</span>
    <span class="chip">시작 시간: {html.escape(str(start_time))}</span>
    <span class="chip">거리: {html.escape(str(distance_text))}</span>
    <span class="chip">시간: {html.escape(str(duration_text))}</span>
  </div>
  <h2>카드</h2>
  {cards_html}
  <h2>제출 이미지</h2>
  <div class="files">
    {files_html}
  </div>
</body>
</html>
"""


def _render_admin_login(path: str, message: str | None = None) -> str:
    message_html = f"<p class=\"message\">{html.escape(message)}</p>" if message else ""
    return f"""
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>운영진 로그인</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #111827; }}
    form {{ display: flex; gap: 8px; align-items: center; }}
    input {{ padding: 8px 10px; border-radius: 8px; border: 1px solid #d1d5db; }}
    button {{ padding: 8px 12px; border-radius: 8px; border: 1px solid #111827; background: #111827; color: #fff; }}
    .message {{ color: #b91c1c; margin-top: 12px; }}
  </style>
</head>
<body>
  <h1>운영진 인증</h1>
  <p>운영진 키를 입력하세요.</p>
  <form method="post" action="/admin/login">
    <input type="password" name="admin_key" placeholder="운영진 키" required />
    <input type="hidden" name="next" value="{html.escape(path)}" />
    <button type="submit">입장</button>
  </form>
  {message_html}
</body>
</html>
"""


def create_app() -> FastAPI:
    base_dir = Path(__file__).resolve().parents[1]
    load_dotenv(base_dir / ".env")
    settings = load_settings(base_dir=base_dir)

    storage = Storage(settings.storage_dir)
    storage.init()

    app = FastAPI(title="MRC Bingo Submit API", version="0.1.0")
    app.state.settings = settings
    app.state.storage = storage
    app.state.base_dir = base_dir

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
    def cards(seed: str | None = None) -> dict[str, Any]:
        resolved_seed = (seed or os.getenv("MRC_SEED", DEFAULT_SEED)).strip() or DEFAULT_SEED
        label_map = build_label_map(resolved_seed)
        return {
            "seed": resolved_seed,
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

    @app.get("/api/v1/progress")
    def progress() -> JSONResponse:
        path = settings.storage_dir / "publish" / "progress.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail="progress not found")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="progress invalid")
        return JSONResponse(content=data)

    @app.get("/api/v1/boards")
    def boards() -> JSONResponse:
        env_path = os.getenv("MRC_BOARDS_PATH")
        boards_dir = settings.storage_dir / "boards"
        path = Path(env_path) if env_path else boards_dir / "boards.json"
        seed = os.getenv("MRC_SEED", DEFAULT_SEED)
        map_labels = (os.getenv("MRC_BOARD_LABEL_MAP") or "").strip().lower() in ("1", "true", "yes", "on")
        carddeck_path = Path(os.getenv("MRC_CARDDECK_PATH", str(app.state.base_dir / "CardDeck.md")))

        # Auto-generate boards.json from the latest upload if needed.
        if env_path is None:
            boards_dir.mkdir(parents=True, exist_ok=True)
            uploads = sorted(boards_dir.glob("upload-*.xlsx"), key=lambda p: p.stat().st_mtime)
            latest_upload = uploads[-1] if uploads else None
            if latest_upload and (not path.exists() or latest_upload.stat().st_mtime > path.stat().st_mtime):
                boards_data = generate_boards_from_xlsx(
                    latest_upload,
                    carddeck_path,
                    label_seed=seed,
                    use_label_map=map_labels,
                )
                write_boards_json(boards_data, path)

        if not path.exists():
            raise HTTPException(status_code=404, detail="boards not found")
        data = load_boards_json(
            path,
            carddeck_path=carddeck_path,
            label_seed=seed,
            apply_label_map=map_labels,
        )
        if not data:
            raise HTTPException(status_code=500, detail="boards invalid")
        return JSONResponse(content=data)

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

        tier_raw = str(form.get("tier") or "").strip()
        if tier_raw:
            try:
                tier = normalize_tier(tier_raw)
            except ValueError:
                raise HTTPException(status_code=400, detail="티어(tier)가 올바르지 않습니다. beginner/intermediate/advanced")
        else:
            tier = _load_tier_from_boards(settings.storage_dir, player_name)
            if not tier:
                raise HTTPException(
                    status_code=400,
                    detail="티어가 없습니다. 빙고판 제출의 '내 티어'를 확인하거나 운영진에 문의하세요.",
                )

        seed = (os.getenv("MRC_SEED", DEFAULT_SEED) or DEFAULT_SEED).strip() or DEFAULT_SEED
        map_labels = (os.getenv("MRC_BOARD_LABEL_MAP") or "").strip().lower() in ("1", "true", "yes", "on")
        carddeck_path = Path(os.getenv("MRC_CARDDECK_PATH", str(app.state.base_dir / "CardDeck.md")))

        token_event = (str(form.get("token_event") or "").strip().lower() or None)
        if token_event not in (None, "earned", "seal", "shield"):
            raise HTTPException(status_code=400, detail="token_event 값이 올바르지 않습니다.")

        claimed_raw = [str(v) for v in form.getlist("claimed_labels")]
        claimed_labels = normalize_claim_labels(_split_csvish(claimed_raw))
        if not claimed_labels and not token_event:
            raise HTTPException(status_code=400, detail="카드 코드(라벨)를 1개 이상 입력하세요.")

        rule_msgs: list[str] = []
        if claimed_labels:
            rules_ok, rule_msgs = validate_claim_labels(claimed_labels)
            if not rules_ok:
                raise HTTPException(status_code=400, detail={"messages": rule_msgs})

        resolved_codes: list[str] = []
        if claimed_labels:
            board_codes_map = _load_board_codes(
                settings.storage_dir,
                carddeck_path=carddeck_path,
                seed=seed,
                map_labels=map_labels,
            )
            player_board_codes = board_codes_map.get(player_name)

            label_map = build_label_map(seed)
            invalid_labels: list[str] = []
            missing_on_board: list[str] = []

            for label in claimed_labels:
                if player_board_codes is not None:
                    if label not in CARDS:
                        invalid_labels.append(label)
                        continue
                    if label not in player_board_codes:
                        missing_on_board.append(label)
                        continue
                    resolved_codes.append(label)
                    continue

                if label in CARDS:
                    resolved_codes.append(label)
                    continue
                if label not in label_map.by_label:
                    invalid_labels.append(label)
                    continue
                resolved_codes.append(label_map.by_label[label])

            if invalid_labels:
                raise HTTPException(
                    status_code=400,
                    detail={"messages": [f"존재하지 않는 카드 코드: {', '.join(invalid_labels)}"]},
                )
            if missing_on_board:
                raise HTTPException(
                    status_code=400,
                    detail={"messages": [f"빙고판에 없는 카드 코드: {', '.join(missing_on_board)}"]},
                )

        group_tiers_raw = _split_csvish([str(v) for v in form.getlist("group_tiers")])
        group_tiers_list = []
        invalid_group_tiers = []
        for raw in group_tiers_raw:
            cleaned = raw.strip()
            if not cleaned:
                continue
            try:
                group_tiers_list.append(normalize_tier(cleaned))
            except ValueError:
                invalid_group_tiers.append(cleaned)
        if invalid_group_tiers:
            raise HTTPException(
                status_code=400,
                detail={"messages": [f"그룹 티어 값이 올바르지 않습니다: {', '.join(invalid_group_tiers)}"]},
            )
        group_tiers = tuple(group_tiers_list) or None

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
            with_new_runner=_parse_bool(form.get("with_new_runner")),
            did_warmup=_parse_bool(form.get("did_warmup")),
            did_cooldown=_parse_bool(form.get("did_cooldown")),
            did_foam_roll=_parse_bool(form.get("did_foam_roll")),
            did_strength=_parse_bool(form.get("did_strength")),
            did_drills=_parse_bool(form.get("did_drills")),
            did_log=_parse_bool(form.get("did_log")),
            is_new_route=_parse_bool(form.get("is_new_route")),
            is_build_up=_parse_bool(form.get("is_build_up")),
            is_pacing=_parse_bool(form.get("is_pacing")),
            is_level_mix=_parse_bool(form.get("is_level_mix")),
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
        if resolved_codes:
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

        summary = {
            "passed": sum(1 for v in validations if v["status"] == "passed"),
            "failed": sum(1 for v in validations if v["status"] == "failed"),
            "needs_review": sum(1 for v in validations if v["status"] == "needs_review"),
        }

        review_cards: dict[str, str] = {}
        for card in validations:
            code = card.get("resolved_code") or card.get("label")
            if not code:
                continue
            review_cards[code] = "pending"

        submission_id = new_submission_id()
        submission_dir = storage.create_submission_dir(submission_id)

        stored_files = []
        for upload in files:
            content = await _read_upload_limited(upload, max_bytes=settings.max_file_bytes)
            stored_files.append(storage.save_file(submission_dir, upload.filename or "upload", content))

        created_at = utc_now_iso()
        notes = str(form.get("notes") or "").strip() or None
        if token_event in ("seal", "shield"):
            available, _, _ = storage.compute_token_balance(player_name=player_name, tier=tier)
            if available <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="사용 가능한 토큰이 없습니다. W 카드 달성 후 다시 시도하세요.",
                )
        token_hold = None
        seal_target = str(form.get("seal_target") or "").strip() or None
        seal_type = (str(form.get("seal_type") or "").strip().upper() or None)
        if seal_type and seal_type not in ("B", "C"):
            raise HTTPException(status_code=400, detail="seal_type 값이 올바르지 않습니다.")
        log_summary = str(form.get("log_summary") or "").strip() or None

        review_status = "pending"
        reviewed_at = None
        reviewed_by = None
        review_notes = None

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
            "claimed_labels": claimed_labels,
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
            "review": {
                "status": review_status,
                "reviewed_at": reviewed_at,
                "reviewed_by": reviewed_by,
                "review_notes": review_notes,
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
            claimed_labels=claimed_labels,
            resolved_codes=resolved_codes,
            validation={"cards": validations},
            notes=notes,
            token_event=token_event,
            token_hold=token_hold,
            seal_target=seal_target,
            seal_type=seal_type,
            log_summary=log_summary,
            review_status=review_status,
            reviewed_at=reviewed_at,
            reviewed_by=reviewed_by,
            review_notes=review_notes,
            review_cards=review_cards,
            files=stored_files,
            user_agent=request.headers.get("user-agent"),
            client_ip=_client_ip(request),
        )
        run_day = _effective_run_day(payload.run_date, created_at)
        if run_day and resolved_codes:
            storage.reject_previous_submissions(
                player_name=player_name,
                keep_id=submission_id,
                run_day=run_day,
                reviewed_at=created_at,
            )

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

    @app.get("/admin")
    def admin(request: Request, status: str = "pending") -> HTMLResponse:
        key = _admin_key_from(request)
        if settings.admin_key and key != settings.admin_key:
            message = "운영진 키가 필요합니다." if not key else "운영진 키가 올바르지 않습니다."
            next_path = request.url.path
            if request.url.query:
                next_path = f"{next_path}?{request.url.query}"
            return HTMLResponse(_render_admin_login(next_path, message), status_code=401)
        status_value = (status or "pending").lower()
        if status_value == "all":
            items = storage.list_submissions(status=None, limit=2000)
        else:
            items = storage.list_submissions(status=status_value, limit=200)
        run_date_filter = (request.query_params.get("run_date") or "").strip() or None
        runner_filter = (request.query_params.get("runner") or "").strip() or None
        index_items = items
        if runner_filter:
            items = [item for item in items if item.get("player_name") == runner_filter]
        if run_date_filter:
            items = [item for item in items if item.get("run_date") == run_date_filter]
        carddeck_path = Path(os.getenv("MRC_CARDDECK_PATH", str(app.state.base_dir / "CardDeck.md")))
        card_titles = _load_card_titles(carddeck_path)
        boards_path = settings.storage_dir / "boards" / "boards.json"
        boards_meta = "none"
        if boards_path.exists():
            try:
                meta = json.loads(boards_path.read_text(encoding="utf-8"))
                boards_meta = _format_boards_meta(meta, boards_path.name)
            except json.JSONDecodeError:
                boards_meta = _format_boards_meta(None, boards_path.name)
        message = request.query_params.get("msg") or ""
        return HTMLResponse(
            _render_admin_page(
                items=items,
                index_items=index_items,
                status=status,
                message=message,
                boards_meta=boards_meta,
                card_titles=card_titles,
                run_date_filter=run_date_filter,
                runner_filter=runner_filter,
                admin_key=key,
            )
        )

    @app.post("/admin/login")
    async def admin_login(request: Request):
        form = await request.form()
        admin_key = str(form.get("admin_key") or "")
        next_path = str(form.get("next") or "/admin")
        if not next_path.startswith("/"):
            next_path = "/admin"
        if settings.admin_key and admin_key != settings.admin_key:
            return HTMLResponse(_render_admin_login(next_path, "운영진 키가 올바르지 않습니다."), status_code=401)
        response = RedirectResponse(url=next_path, status_code=303)
        max_age = _parse_int(os.getenv("MRC_ADMIN_COOKIE_MAX_AGE")) or 60 * 60 * 12
        secure_flag = _parse_bool(os.getenv("MRC_ADMIN_COOKIE_SECURE")) or _is_secure_request(request)
        response.set_cookie(
            ADMIN_COOKIE_NAME,
            admin_key,
            max_age=max_age,
            httponly=True,
            samesite="lax",
            secure=secure_flag,
            path="/",
        )
        return response

    @app.get("/admin/submissions/{submission_id}")
    def admin_submission(submission_id: str, request: Request) -> HTMLResponse:
        key = _admin_key_from(request)
        if settings.admin_key and key != settings.admin_key:
            message = "운영진 키가 필요합니다." if not key else "운영진 키가 올바르지 않습니다."
            next_path = request.url.path
            if request.url.query:
                next_path = f"{next_path}?{request.url.query}"
            return HTMLResponse(_render_admin_login(next_path, message), status_code=401)
        meta = _load_submission_meta(storage, submission_id)
        if not meta:
            raise HTTPException(status_code=404, detail="submission not found")
        carddeck_path = Path(os.getenv("MRC_CARDDECK_PATH", str(app.state.base_dir / "CardDeck.md")))
        card_titles = _load_card_titles(carddeck_path)
        return HTMLResponse(
            _render_admin_submission_page(
                submission_id=submission_id,
                meta=meta,
                card_titles=card_titles,
            )
        )

    @app.get("/admin/submissions/{submission_id}/files/{file_index}")
    def admin_submission_file(submission_id: str, file_index: int, request: Request) -> FileResponse:
        _require_admin(settings, request)
        meta = _load_submission_meta(storage, submission_id)
        if not meta:
            raise HTTPException(status_code=404, detail="submission not found")
        files = meta.get("files") or []
        if file_index < 0 or file_index >= len(files):
            raise HTTPException(status_code=404, detail="file not found")
        stored_as = files[file_index].get("stored_as")
        if not stored_as:
            raise HTTPException(status_code=404, detail="file not found")
        submission_dir = storage.submissions_dir / submission_id
        file_path = (submission_dir / stored_as).resolve()
        try:
            file_path.relative_to(submission_dir.resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid file path")
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="file not found")
        media_type, _ = mimetypes.guess_type(str(file_path))
        return FileResponse(file_path, media_type=media_type or "application/octet-stream")

    @app.post("/admin/review/{submission_id}")
    async def admin_review(submission_id: str, request: Request) -> RedirectResponse:
        form = await request.form()
        key = _require_admin(settings, request, dict(form))
        run_date = (request.query_params.get("run_date") or "").strip() or None
        runner = (request.query_params.get("runner") or "").strip() or None
        status = (form.get("review_status") or "").strip().lower()
        if status not in ("approved", "rejected", "pending"):
            raise HTTPException(status_code=400, detail="review_status invalid")
        card_code = (form.get("card_code") or "").strip() or None
        reviewer = str(form.get("reviewer") or "").strip() or None
        notes = str(form.get("review_notes") or "").strip() or None
        if card_code:
            storage.update_card_review_status(
                submission_id=submission_id,
                card_code=card_code,
                status=status,
                reviewed_at=utc_now_iso(),
                reviewed_by=reviewer,
                review_notes=notes,
            )
            message = f"카드 리뷰 업데이트 완료 ({card_code})"
        else:
            storage.update_review_status(
                submission_id=submission_id,
                status=status,
                reviewed_at=utc_now_iso(),
                reviewed_by=reviewer,
                review_notes=notes,
            )
            message = "리뷰 업데이트 완료"
        if _parse_bool(os.getenv("MRC_ADMIN_AUTO_PUBLISH")):
            _, publish_message = _run_publish_now(settings.storage_dir)
            message = f"{message} · {publish_message}"
        redirect = f"/admin?{_build_admin_query(status=status, run_date=run_date, runner=runner, msg=message)}"
        return RedirectResponse(url=redirect, status_code=303)

    @app.post("/admin/publish")
    async def admin_publish(
        request: Request,
        status: str = "pending",
        admin_key: str = Form(""),
    ) -> RedirectResponse:
        form = await request.form()
        key = _require_admin(settings, request, dict(form) | {"admin_key": admin_key})
        run_date = (request.query_params.get("run_date") or "").strip() or None
        runner = (request.query_params.get("runner") or "").strip() or None
        _, message = _run_publish_now(settings.storage_dir)
        redirect = f"/admin?{_build_admin_query(status=status, run_date=run_date, runner=runner, msg=message)}"
        return RedirectResponse(url=redirect, status_code=303)

    @app.post("/admin/boards/upload")
    async def admin_boards_upload(
        request: Request,
        file: UploadFile = File(...),
        admin_key: str = Form(""),
    ) -> RedirectResponse:
        key = _require_admin(settings, request, {"admin_key": admin_key})
        if not file.filename:
            raise HTTPException(status_code=400, detail="file required")
        data = await file.read()
        boards_dir = settings.storage_dir / "boards"
        boards_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(file.filename).name.replace("/", "_").replace("\\", "_")
        upload_path = boards_dir / f"upload-{safe_name}"
        upload_path.write_bytes(data)

        carddeck_path = Path(os.getenv("MRC_CARDDECK_PATH", str(app.state.base_dir / "CardDeck.md")))
        seed = os.getenv("MRC_SEED", DEFAULT_SEED)
        use_label_map = (os.getenv("MRC_BOARD_LABEL_MAP") or "").strip().lower() in ("1", "true", "yes", "on")
        boards_data = generate_boards_from_xlsx(
            upload_path,
            carddeck_path,
            label_seed=seed,
            use_label_map=use_label_map,
        )
        out_path = boards_dir / "boards.json"
        write_boards_json(boards_data, out_path)

        redirect = "/admin?status=pending&msg=boards+updated"
        return RedirectResponse(url=redirect, status_code=303)

    return app
