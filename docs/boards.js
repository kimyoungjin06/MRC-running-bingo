const DEFAULT_DATA_URL = "./data/boards.json";
const DEFAULT_API_BASE = "https://scanned-sticker-chuck-liabilities.trycloudflare.com";
const DEFAULT_API_URL = `${DEFAULT_API_BASE}/api/v1/boards`;
const DEFAULT_TIER_URL = "./data/tiers.json";
const DEFAULT_PROGRESS_URL = "./data/progress.json";
const AUTO_REFRESH_MS = 60000;
const DEFAULT_SEED = "2025W";
const CARDDECK_URL = "./content/carddeck.md";

const labelMapCache = new Map();
let cardDeckCache = null;
let cardDeckPromise = null;

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
  return base ? `${base}/api/v1/boards` : DEFAULT_DATA_URL;
}

function getProgressUrl() {
  const params = new URLSearchParams(window.location.search);
  const queryUrl = params.get("progress");
  if (queryUrl) return queryUrl;
  const base = getApiBase();
  return base ? `${base}/api/v1/progress` : DEFAULT_PROGRESS_URL;
}

const DATA_URL = getDataUrl();
const PROGRESS_URL = getProgressUrl();

const refs = {
  boardsContainer: document.getElementById("boardsContainer"),
  boardsMessage: document.getElementById("boardsMessage"),
  boardsCount: document.getElementById("boardsCount"),
  boardSearch: document.getElementById("boardSearch"),
};

let allBoards = [];
let progressLookup = { byId: new Map(), byName: new Map() };
let noticeMessage = "";
let tierLookup = new Map();

function setMessage(text) {
  refs.boardsMessage.textContent = text || "";
}

function setNotice(text) {
  noticeMessage = text || "";
}

function formatTimestamp(value) {
  if (!value) return "";
  if (value.includes("T")) return value.replace("T", " ").slice(0, 16);
  return value;
}

function formatTier(board) {
  if (!board) return "";
  if (board.tier_label) return board.tier_label;
  const tier = (board.tier || "").toString().toLowerCase();
  if (tier === "beginner") return "초보";
  if (tier === "intermediate") return "중수";
  if (tier === "advanced") return "고수";
  return "";
}

function hashString(value) {
  let h = 2166136261;
  for (let i = 0; i < value.length; i++) {
    h ^= value.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function mulberry32(seed) {
  return function () {
    let t = (seed += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffleInPlace(items, rng) {
  for (let i = items.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [items[i], items[j]] = [items[j], items[i]];
  }
}

function parseCardDeck(text) {
  const map = new Map();
  const pattern = /^([ABCDW]\d{2})\s+(★+)\s+(.+)$/;
  text.split(/\r?\n/).forEach((line) => {
    const trimmed = line.trim();
    const match = trimmed.match(pattern);
    if (!match) return;
    const code = match[1];
    const stars = match[2].length;
    const title = match[3].trim();
    map.set(code, { code, type: code[0], stars, title });
  });
  return map;
}

async function loadCardDeck() {
  if (cardDeckCache) return cardDeckCache;
  if (!cardDeckPromise) {
    cardDeckPromise = fetch(CARDDECK_URL, { cache: "no-store" })
      .then((res) => {
        if (!res.ok) throw new Error("card deck load failed");
        return res.text();
      })
      .then((text) => {
        cardDeckCache = parseCardDeck(text);
        return cardDeckCache;
      })
      .catch(() => {
        cardDeckCache = null;
        return null;
      });
  }
  return cardDeckPromise;
}

function buildLabelMap(seed, cardDeck) {
  const rng = mulberry32(hashString(seed));
  const byId = new Map();
  const byLabel = new Map();
  const codesByType = { A: [], B: [], C: [], D: [], W: [] };

  for (const code of cardDeck.keys()) {
    const type = code[0];
    if (codesByType[type]) codesByType[type].push(code);
  }

  Object.keys(codesByType).forEach((type) => {
    const codes = codesByType[type].slice().sort();
    const labels = codes.slice();
    shuffleInPlace(labels, rng);
    codes.forEach((code, idx) => {
      const label = labels[idx];
      byId.set(code, label);
      byLabel.set(label, code);
    });
  });

  return { seed, byId, byLabel };
}

function getLabelMap(seed, cardDeck) {
  if (labelMapCache.has(seed)) return labelMapCache.get(seed);
  const map = buildLabelMap(seed, cardDeck);
  labelMapCache.set(seed, map);
  return map;
}

function hasLabelFields(data) {
  const boards = Array.isArray(data?.boards) ? data.boards : [];
  for (const board of boards) {
    const grid = Array.isArray(board?.grid) ? board.grid : [];
    for (const row of grid) {
      for (const cell of row || []) {
        if (cell && typeof cell === "object" && "label" in cell) return true;
      }
    }
  }
  return false;
}

function buildTierLookup(data) {
  const map = new Map();
  const items = Array.isArray(data?.tiers) ? data.tiers : [];
  items.forEach((item) => {
    const name = (item?.name || "").trim();
    if (!name) return;
    const label = item?.label || "";
    const tier = item?.tier || "";
    map.set(name, label || tier);
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

async function applyLabelMapIfNeeded(data) {
  if (!data || typeof data !== "object") return false;
  if (data.label_map_applied || data.code_basis === "actual" || hasLabelFields(data)) return false;

  const seed = String(data.label_map_seed || DEFAULT_SEED).trim() || DEFAULT_SEED;
  const cardDeck = await loadCardDeck();
  if (!cardDeck || cardDeck.size === 0) return false;

  const labelMap = getLabelMap(seed, cardDeck);
  let updated = false;
  const boards = Array.isArray(data.boards) ? data.boards : [];

  boards.forEach((board) => {
    const grid = Array.isArray(board?.grid) ? board.grid : [];
    grid.forEach((row) => {
      (row || []).forEach((cell) => {
        if (!cell || typeof cell !== "object") return;
        const label = cell.code;
        if (!label) return;
        const actual = labelMap.byLabel.get(label);
        if (!actual) return;

        const card = cardDeck.get(actual);
        if (card) {
          cell.type = card.type;
          cell.stars = card.stars;
          cell.title = card.title;
        }

        if (actual !== label) {
          cell.label = cell.label || label;
          cell.code = actual;
          updated = true;
        }
      });
    });
  });

  if (updated) {
    data.label_map_applied = true;
    data.code_basis = "actual";
    data.label_map_seed = seed;
  }
  return updated;
}

function createCell(cell, isChecked) {
  const div = document.createElement("div");
  div.className = "board-cell board-cell--static";
  if (cell.type) {
    div.classList.add(`board-cell--${cell.type}`);
  }
  if (isChecked) {
    div.classList.add("board-cell--checked");
  }

  const code = document.createElement("div");
  code.className = "board-cell__code";
  code.textContent = cell.code || cell.raw || "—";

  const stars = document.createElement("div");
  stars.className = "board-cell__stars";
  stars.textContent = cell.stars ? "★".repeat(cell.stars) : "";

  const title = document.createElement("div");
  title.className = "board-cell__title";
  title.textContent = cell.title || "";

  div.append(code, stars, title);
  return div;
}

function getProgressForBoard(board) {
  if (board.player_id && progressLookup.byId.has(board.player_id)) {
    return progressLookup.byId.get(board.player_id);
  }
  if (board.name && progressLookup.byName.has(board.name)) {
    return progressLookup.byName.get(board.name);
  }
  return null;
}

function createBoardCard(board) {
  const progress = getProgressForBoard(board);
  const checkedCodes = new Set(progress?.checked_codes || []);

  const wrap = document.createElement("section");
  wrap.className = "board-card";

  const header = document.createElement("div");
  header.className = "board-card__header";

  const titleWrap = document.createElement("div");
  titleWrap.className = "board-card__title-wrap";

  const title = document.createElement("div");
  title.className = "board-card__title";
  title.textContent = board.name || "이름 없음";

  titleWrap.appendChild(title);
  const tierLabel = formatTier(board);
  if (tierLabel) {
    const tierBadge = document.createElement("span");
    tierBadge.className = "board-card__badge";
    tierBadge.textContent = tierLabel;
    titleWrap.appendChild(tierBadge);
  }

  if (checkedCodes.size > 0) {
    const badge = document.createElement("span");
    badge.className = "board-card__badge";
    badge.textContent = progress?.example ? "진행도 예시" : `진행도 ${checkedCodes.size}`;
    titleWrap.appendChild(badge);
  }

  const meta = document.createElement("div");
  meta.className = "board-card__meta";
  const ts = formatTimestamp(board.timestamp);
  meta.textContent = ts ? `제출: ${ts}` : "제출 시간 없음";

  header.append(titleWrap, meta);

  const grid = document.createElement("div");
  grid.className = "board board--public";
  board.grid.forEach((row) => {
    row.forEach((cell) => grid.append(createCell(cell, checkedCodes.has(cell.code))));
  });

  wrap.append(header, grid);
  return wrap;
}

function renderBoards(filterText) {
  const keyword = (filterText || "").trim();
  refs.boardsContainer.innerHTML = "";

  const filtered = allBoards.filter((board) => {
    if (!keyword) return true;
    return (board.name || "").includes(keyword);
  });

  refs.boardsCount.textContent = `${filtered.length} boards`;

  if (filtered.length === 0) {
    const base = keyword ? "검색 결과가 없습니다." : "표시할 빙고판이 없습니다.";
    setMessage(noticeMessage ? `${noticeMessage} · ${base}` : base);
    return;
  }

  setMessage(noticeMessage);
  filtered.forEach((board) => refs.boardsContainer.append(createBoardCard(board)));
}

async function loadBoards() {
  try {
    let usedFallback = false;
    const boardsJson = await fetch(DATA_URL, { cache: "no-store" })
      .then((res) => {
        if (!res.ok) throw new Error(`데이터 로드 실패: ${res.status}`);
        return res.json();
      })
      .catch(async () => {
        if (DATA_URL !== DEFAULT_API_URL) {
          const res = await fetch(DEFAULT_API_URL, { cache: "no-store" });
          if (res.ok) return res.json();
        }
        if (DATA_URL === DEFAULT_DATA_URL) throw new Error("boards fallback failed");
        usedFallback = true;
        const res = await fetch(DEFAULT_DATA_URL, { cache: "no-store" });
        if (!res.ok) throw new Error(`데이터 로드 실패: ${res.status}`);
        return res.json();
      });
    await applyLabelMapIfNeeded(boardsJson);
    allBoards = Array.isArray(boardsJson.boards) ? boardsJson.boards : [];
    tierLookup = await loadTierFallback();
    if (tierLookup.size > 0) {
      allBoards.forEach((board) => {
        if (!board || board.tier_label || board.tier) return;
        const label = tierLookup.get(board.name);
        if (label) board.tier_label = label;
      });
    }

    progressLookup = { byId: new Map(), byName: new Map() };
    try {
      let progressFallback = false;
      const progressJson = await fetch(PROGRESS_URL, { cache: "no-store" })
        .then((res) => {
          if (!res.ok) throw new Error(`progress load failed: ${res.status}`);
          return res.json();
        })
        .catch(async () => {
          if (PROGRESS_URL === DEFAULT_PROGRESS_URL) throw new Error("progress fallback failed");
          progressFallback = true;
          const res = await fetch(DEFAULT_PROGRESS_URL, { cache: "no-store" });
          if (!res.ok) throw new Error(`progress load failed: ${res.status}`);
          return res.json();
        });
      const players = Array.isArray(progressJson.players) ? progressJson.players : [];
      players.forEach((player) => {
        if (player.id) progressLookup.byId.set(player.id, player);
        if (player.name) progressLookup.byName.set(player.name, player);
      });
      usedFallback = usedFallback || progressFallback;
    } catch {
      progressLookup = { byId: new Map(), byName: new Map() };
    }

    setNotice(usedFallback ? "서버 접속 불가: 예시 데이터 표시 중" : "");
    renderBoards(refs.boardSearch.value);
  } catch (err) {
    setMessage("boards.json을 불러오지 못했습니다. 서버 주소 또는 업로드 상태를 확인하세요.");
  }
}

function init() {
  refs.boardSearch.addEventListener("input", (e) => renderBoards(e.target.value));
  loadBoards();
  if (AUTO_REFRESH_MS > 0) {
    setInterval(loadBoards, AUTO_REFRESH_MS);
  }
}

document.addEventListener("DOMContentLoaded", init);
