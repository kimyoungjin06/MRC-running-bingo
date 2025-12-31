# data 구조 안내

이 폴더는 GitHub Pages에서 사용하는 공개 데이터(JSON)를 보관합니다.

## boards.json
- `generated_at`: 생성 시각(ISO)
- `source`: 원본 파일 경로
- `boards[]`
  - `id`: 보드 ID (stable)
  - `player_id`: 플레이어 ID (stable)
  - `name`: 참가자 이름
  - `timestamp`: 제출 시각(ISO)
  - `email`: 이메일(있을 때만)
  - `grid[5][5]`
    - `raw`: 원본 셀 텍스트
    - `code`: 카드 코드 (예: A02)
    - `type`: 카드 타입 (A/B/C/D/W)
    - `stars`: 난이도 별 수
    - `title`: 카드 앞면 제목

## progress.json
- `version`: 스키마 버전
- `seed`: 시즌 시드
- `generated_at`: 생성 시각(ISO)
- `summary`: 전체 요약 지표
- `attack_logs[]`: Seal 기록
- `token_holds[]`: 토큰 보유 현황
- `latest_logs[]`: 최신 로그
- `players[]`
  - `id`, `name`
  - `checked`: 체크된 칸 수
  - `bingo`: 빙고 라인 수
  - `stars`: 별 합계
  - `tokens`: 현재 토큰 수
  - `last_update`
  - `checked_codes[]`: 체크된 카드 코드 리스트
  - `achievements`: 5빙고/올빙고 등 달성 정보
  - `example`: 예시 데이터 여부
