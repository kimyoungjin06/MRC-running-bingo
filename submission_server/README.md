# MRC Bingo 제출/검증 API (로컬 PC용)

GitHub Pages(웹 UI)에서 **스크린샷/메타데이터 업로드**를 받아 로컬 PC에 저장하고, 기본 규칙(A/B/C 1회당 2칸 등)과 일부 카드 조건을 자동 검증하는 작은 API 서버입니다.

## 1) 설치/실행

```bash
cd submission_server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
python main.py
```

만약 `python3 -m venv`에서 `ensurepip is not available` 오류가 나면(일부 WSL/리눅스 최소 설치):

```bash
python3 -m venv --without-pip .venv
source .venv/bin/activate
curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
python /tmp/get-pip.py
pip install -r requirements.txt
```

실행 후:
- Health: `http://localhost:8787/healthz`

## 2) 외부에서 접속 가능하게 열기(권장: HTTPS 터널)

GitHub Pages에서 호출하려면 **공인 HTTPS URL**이 필요합니다. 예시(Cloudflare Tunnel):

```bash
cloudflared tunnel --url http://localhost:8787
```

표시되는 `https://....trycloudflare.com` URL을 `docs/submit.html`의 API 주소로 넣으면 됩니다.

---

## 2-1) AWS EC2 운영 (Docker Compose)

AWS에서 운영하려면 `AWS_EC2.md` 가이드를 참고하세요.

```bash
cd submission_server
cp .env.aws.example .env
docker compose up -d --build
```

운영진 UI:
- `https://<domain>/admin` 접속 후 운영진 키 입력

보드 업로드:
- `MRC_CARDDECK_PATH`가 올바른지 확인(로컬: `../CardDeck.md`, Docker: `/app/CardDeck.md`)
- 라벨 셔플을 쓴 경우: `MRC_BOARD_LABEL_MAP=1`, `MRC_SEED=2025W` 설정 후 업로드
  - 업로드 전 데이터가 라벨이어도, API/검증 단계에서 자동 매핑됩니다.

## 3) 보안(최소한의 스팸 방지)

`.env`의 `MRC_SUBMIT_API_KEY`를 설정하면 제출 시 키가 필요합니다.
- 헤더: `X-MRC-Submit-Key: <키>` 또는
- 폼 필드: `submit_key=<키>`

## 4) API 요약

- `GET /healthz`
- `GET /api/v1/cards?seed=2025W` : 카드 목록(+라벨 셔플 매핑)
- `POST /api/v1/submissions` : 스크린샷 + 메타 + 체크하려는 카드(최대 2개) 업로드
- `GET /api/v1/progress` : publish된 진행도 JSON
- `GET /api/v1/boards` : 업로드된 빙고판 JSON

운영진:
- `GET /admin` : 제출 목록/검토
- `POST /admin/review/{submission_id}` : 승인/반려
- `POST /admin/boards/upload` : 빙고판 xlsx 업로드

업로드는 `storage/submissions/<id>/` 아래에 저장됩니다.

### 추가 제출 필드(선택)
- `token_event`: `earned` / `seal` / `shield`
- `token_hold`: `0` / `1`
- `seal_target`: Seal 대상 이름
- `seal_type`: `B` / `C`
- `log_summary`: 최신 로그 요약
