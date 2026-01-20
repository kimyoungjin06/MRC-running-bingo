const DEFAULT_DATA_URL = "./data/progress.json";
const DEFAULT_API_BASE = "https://listing-proceed-rated-pills.trycloudflare.com";
const DEFAULT_API_URL = `${DEFAULT_API_BASE}/api/v1/progress`;
const DEFAULT_BOARDS_URL = "./data/boards.json";
const DEFAULT_BOARDS_API_URL = `${DEFAULT_API_BASE}/api/v1/boards`;
const DEFAULT_TIER_URL = "./data/tiers.json";

function normalizeBaseUrl(url) {
  return (url || "").trim().replace(/\/+$/, "");
}

function getApiBase() {
  const stored = localStorage.getItem("mrc_submit_api_base");
  if (stored === null) return normalizeBaseUrl(DEFAULT_API_BASE);
  return normalizeBaseUrl(stored);
}

function getDataUrl() {
  const params = new URLSearchParams(window.location.search);
  const queryUrl = params.get("data");
  if (queryUrl) return queryUrl;
  const base = getApiBase();
  return base ? `${base}/api/v1/progress` : DEFAULT_DATA_URL;
}

const DATA_URL = getDataUrl();

const refs = {
  generatedAt: document.getElementById("generatedAt"),
  summaryCounts: document.getElementById("summaryCounts"),
  attackList: document.getElementById("attackList"),
  tokenList: document.getElementById("tokenList"),
  latestList: document.getElementById("latestList"),
  topMessage: document.getElementById("topMessage"),
  sprintLanes: document.getElementById("sprintLanes"),
  sprintAxis: document.getElementById("sprintAxis"),
  sprintMessage: document.getElementById("sprintMessage"),
  progressTable: document.getElementById("progressTable"),
  progressMessage: document.getElementById("progressMessage"),
  progressSearch: document.getElementById("progressSearch"),
};

let allPlayers = [];
let tierLookup = new Map();

function setMessage(el, text) {
  el.textContent = text || "";
}

function formatTime(value) {
  if (!value) return "";
  if (value.includes("T")) return value.replace("T", " ").slice(0, 16);
  return value;
}

function normalizeTierLabel(value) {
  const raw = (value || "").toString().trim();
  if (!raw) return "";
  const lowered = raw.toLowerCase();
  if (lowered === "beginner") return "초보";
  if (lowered === "intermediate") return "중수";
  if (lowered === "advanced") return "고수";
  return raw;
}

function buildTierLookup(data) {
  const map = new Map();
  const items = Array.isArray(data?.tiers) ? data.tiers : [];
  items.forEach((item) => {
    const name = (item?.name || "").trim();
    if (!name) return;
    const label = normalizeTierLabel(item?.label || item?.tier || "");
    if (label) map.set(name, label);
  });
  return map;
}

async function loadTierFallback() {
  try {
    const res = await fetch(DEFAULT_TIER_URL, { cache: "no-store" });
    if (!res.ok) return new Map();
    const data = await res.json();
    return buildTierLookup(data);
  } catch {
    return new Map();
  }
}

async function loadTierFromBoards(baseUrl) {
  const url = baseUrl ? `${baseUrl}/api/v1/boards` : DEFAULT_BOARDS_API_URL;
  try {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error("boards load failed");
    const data = await res.json();
    const map = new Map();
    const boards = Array.isArray(data?.boards) ? data.boards : [];
    boards.forEach((board) => {
      const name = (board?.name || "").trim();
      if (!name) return;
      const label = normalizeTierLabel(board?.tier_label || board?.tier || "");
      if (label) map.set(name, label);
    });
    return map;
  } catch {
    return new Map();
  }
}

function getTierLabel(player) {
  const name = (player?.name || "").trim();
  if (!name) return "-";
  return tierLookup.get(name) || "-";
}

function getCheckedCount(player) {
  if (typeof player.checked === "number") return player.checked;
  if (Array.isArray(player.checked_codes)) return player.checked_codes.length;
  return 0;
}

function renderSummary(summary) {
  const items = [
    { label: "참가자", value: summary.total_players ?? 0 },
    { label: "체크", value: summary.total_checked ?? 0 },
    { label: "별", value: summary.total_stars ?? 0 },
  ];
  refs.summaryCounts.innerHTML = "";
  items.forEach((item) => {
    const div = document.createElement("div");
    div.className = "count-item";
    div.innerHTML = `<span>${item.label}</span><strong>${item.value}</strong>`;
    refs.summaryCounts.appendChild(div);
  });
}

function renderList(listEl, items, emptyText, formatFn) {
  listEl.innerHTML = "";
  if (!items || items.length === 0) {
    const li = document.createElement("li");
    li.className = "muted";
    li.textContent = emptyText;
    listEl.appendChild(li);
    return;
  }
  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = formatFn(item);
    listEl.appendChild(li);
  });
}

function renderTop(data) {
  renderList(
    refs.attackList,
    data.attack_logs || [],
    "기록 없음",
    (item) => `${formatTime(item.time)} · ${item.actor} → ${item.target} (${item.seal_type || "-"})`
  );
  renderList(
    refs.tokenList,
    data.token_holds || [],
    "보유 현황 없음",
    (item) =>
      `${item.name} · ${item.hold ?? "-"}개${item.cap ? `/${item.cap}` : ""} (${item.event || "상태"})`
  );
  renderList(
    refs.latestList,
    data.latest_logs || [],
    "로그 없음",
    (item) => `${formatTime(item.time)} · ${item.player}: ${item.message}`
  );
}

function renderSprint(players) {
  if (!refs.sprintLanes || !refs.sprintAxis) return;
  refs.sprintLanes.innerHTML = "";
  refs.sprintAxis.innerHTML = "";

  const maxCells = 25;
  for (let i = 0; i <= maxCells; i += 1) {
    const tick = document.createElement("span");
    tick.textContent = String(i);
    refs.sprintAxis.appendChild(tick);
  }

  if (!players || players.length === 0) {
    setMessage(refs.sprintMessage, "진행도 데이터가 없습니다.");
    return;
  }
  setMessage(refs.sprintMessage, "");

  const sorted = [...players].sort((a, b) => getCheckedCount(b) - getCheckedCount(a));
  sorted.forEach((player) => {
    const checked = getCheckedCount(player);
    const progress = Math.max(0, Math.min(checked, maxCells)) / maxCells;
    const percent = `${(progress * 100).toFixed(1)}%`;
    const lane = document.createElement("div");
    lane.className = "sprint-lane";
    lane.style.setProperty("--progress", percent);
    lane.innerHTML = `
      <div class="sprint-lane__header">
        <span class="sprint-lane__name">${player.name || "-"}</span>
        <span class="sprint-lane__value">${checked}/${maxCells}</span>
      </div>
      <div class="sprint-track">
        <div class="sprint-track__progress"></div>
        <div class="sprint-track__line"></div>
        <div class="sprint-runner" aria-hidden="true"></div>
      </div>
    `;
    refs.sprintLanes.appendChild(lane);
  });
}

function renderProgressTable(players, keyword) {
  refs.progressTable.innerHTML = "";
  const filtered = players.filter((player) => {
    if (!keyword) return true;
    return (player.name || "").includes(keyword);
  });

  if (filtered.length === 0) {
    setMessage(refs.progressMessage, keyword ? "검색 결과가 없습니다." : "진행도 데이터가 없습니다.");
    return;
  }

  setMessage(refs.progressMessage, "");
  const table = document.createElement("div");
  table.className = "progress-table__grid";
  table.innerHTML = `
    <div class="progress-row progress-row--header">
      <span>이름</span>
      <span>티어</span>
      <span>체크</span>
      <span>빙고</span>
      <span>별</span>
      <span>토큰</span>
      <span>업적</span>
      <span>최근</span>
    </div>
  `;

  filtered.forEach((player) => {
    const checked = getCheckedCount(player);
    const stars = player.stars ?? 0;
    const tokens = player.tokens ?? 0;
    const tokenCap = player.token_cap ?? null;
    const achievements = player.achievements || {};
    const badges = [];
    if (achievements.first_bingo5) badges.push('<span class="badge badge--first">퍼스트 5빙고</span>');
    if (achievements.first_full) badges.push('<span class="badge badge--first">퍼스트 올빙고</span>');
    if (achievements.bingo5) badges.push('<span class="badge badge--bingo">5빙고</span>');
    if (achievements.full) badges.push('<span class="badge badge--full">올빙고</span>');
    const badgeHtml = badges.length ? badges.join(" ") : '<span class="muted">-</span>';
    const row = document.createElement("div");
    row.className = `progress-row${achievements.first_bingo5 || achievements.first_full ? " progress-row--first" : ""}`;
    row.innerHTML = `
      <span>${player.name || "-"}</span>
      <span>${getTierLabel(player)}</span>
      <span>${checked}</span>
      <span>${player.bingo ?? 0}</span>
      <span>${stars}</span>
      <span>${tokenCap ? `${tokens}/${tokenCap}` : tokens}</span>
      <span class="progress-badges">${badgeHtml}</span>
      <span>${formatTime(player.last_update || "")}</span>
    `;
    table.appendChild(row);
  });

  refs.progressTable.appendChild(table);
}

async function loadProgress() {
  try {
    let usedFallback = false;
    const data = await fetch(DATA_URL, { cache: "no-store" })
      .then((res) => {
        if (!res.ok) throw new Error(`데이터 로드 실패: ${res.status}`);
        return res.json();
      })
      .catch(async () => {
        if (DATA_URL !== DEFAULT_API_URL) {
          const res = await fetch(DEFAULT_API_URL, { cache: "no-store" });
          if (res.ok) return res.json();
        }
        if (DATA_URL === DEFAULT_DATA_URL) throw new Error("progress fallback failed");
        usedFallback = true;
        const res = await fetch(DEFAULT_DATA_URL, { cache: "no-store" });
        if (!res.ok) throw new Error(`데이터 로드 실패: ${res.status}`);
        return res.json();
      });

    refs.generatedAt.textContent = `최근 업데이트: ${formatTime(data.generated_at) || "-"}`;
    const base = getApiBase();
    tierLookup = await loadTierFromBoards(base);
    if (tierLookup.size === 0) {
      tierLookup = await loadTierFallback();
    }
    renderSummary(data.summary || {});
    renderTop(data);

    allPlayers = Array.isArray(data.players) ? data.players : [];
    renderSprint(allPlayers);
    renderProgressTable(allPlayers, refs.progressSearch.value.trim());
    setMessage(refs.topMessage, usedFallback ? "서버 접속 불가: 예시 데이터 표시 중" : "");
  } catch (err) {
    setMessage(refs.topMessage, "progress.json을 불러오지 못했습니다. 매일 업데이트 후 다시 확인하세요.");
    setMessage(refs.progressMessage, "progress.json을 불러오지 못했습니다.");
    setMessage(refs.sprintMessage, "progress.json을 불러오지 못했습니다.");
  }
}

function init() {
  refs.progressSearch.addEventListener("input", (e) => {
    renderProgressTable(allPlayers, e.target.value.trim());
  });
  loadProgress();
}

document.addEventListener("DOMContentLoaded", init);
