const DATA_URL = "./data/progress.json";

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

function setMessage(el, text) {
  el.textContent = text || "";
}

function formatTime(value) {
  if (!value) return "";
  if (value.includes("T")) return value.replace("T", " ").slice(0, 16);
  return value;
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
    (item) => `${item.name} · ${item.hold ?? "-"}개 (${item.event || "상태"})`
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
      <span>체크</span>
      <span>빙고</span>
      <span>별</span>
      <span>토큰</span>
      <span>최근</span>
    </div>
  `;

  filtered.forEach((player) => {
    const checked = getCheckedCount(player);
    const stars = player.stars ?? 0;
    const tokens = player.tokens ?? 0;
    const row = document.createElement("div");
    row.className = "progress-row";
    row.innerHTML = `
      <span>${player.name || "-"}</span>
      <span>${checked}</span>
      <span>${player.bingo ?? 0}</span>
      <span>${stars}</span>
      <span>${tokens}</span>
      <span>${formatTime(player.last_update || "")}</span>
    `;
    table.appendChild(row);
  });

  refs.progressTable.appendChild(table);
}

async function loadProgress() {
  try {
    const res = await fetch(DATA_URL, { cache: "no-store" });
    if (!res.ok) throw new Error(`데이터 로드 실패: ${res.status}`);
    const data = await res.json();

    refs.generatedAt.textContent = `최근 업데이트: ${formatTime(data.generated_at) || "-"}`;
    renderSummary(data.summary || {});
    renderTop(data);

    allPlayers = Array.isArray(data.players) ? data.players : [];
    renderSprint(allPlayers);
    renderProgressTable(allPlayers, refs.progressSearch.value.trim());
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
