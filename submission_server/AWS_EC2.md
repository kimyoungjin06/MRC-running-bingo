# AWS EC2 운영 가이드 (A안)

이 가이드는 EC2 + Docker Compose로 제출/운영 서버를 실행하는 방법입니다.

## 1) EC2 준비
- Ubuntu 22.04 LTS 권장
- 보안 그룹: 22(SSH), 80/443(HTTPS용), 8787(직접 접근 필요 시) 열기
- 도메인 사용 시 A 레코드로 EC2 퍼블릭 IP 연결

## 2) Docker 설치

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
```

SSH 재접속 후 `docker version` 확인하세요.

## 3) 배포

```bash
git clone <your-repo-url>
cd MRC-running-bingo/submission_server

cp .env.aws.example .env
# .env 편집: MRC_SUBMIT_ALLOWED_ORIGINS, MRC_SUBMIT_API_KEY, MRC_ADMIN_KEY 등 설정

docker compose up -d --build
```

`CardDeck.md`는 상위 폴더에 있어야 하며, `docker-compose.yml`이 자동으로 `/app/CardDeck.md`로 마운트합니다.

라벨 셔플(뒷면 코드)을 썼다면 `.env`에 아래를 추가:
```
MRC_SEED=2025W
MRC_BOARD_LABEL_MAP=1
```

헬스 체크:
- `http://<EC2_IP>:8787/healthz`

## 4) HTTPS 설정(권장)
GitHub Pages에서 호출하려면 HTTPS가 필요합니다.

옵션 A) 리버스 프록시(권장)
- Nginx + Certbot 또는 Caddy 사용
- 리버스 프록시가 `http://localhost:8787`로 전달

옵션 B) Cloudflare Tunnel
- 도메인이 없을 때 임시/저렴한 방법

## 5) 운영 흐름
- 새벽 01:00 KST: 전처리 job 실행
- 오전: 운영진 검토(/admin) 후 승인
- 13:00 KST: publish job 실행 (progress.json 생성)

운영진 UI:
- `https://<domain>/admin` 접속 후 운영진 키 입력

## 6) 점검/로그

```bash
docker compose logs -f api
docker compose logs -f scheduler
```
