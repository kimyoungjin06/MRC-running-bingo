const DATA_URL = "./data/boards.json";
const PROGRESS_URL = "./data/progress.json";

const refs = {
  boardsContainer: document.getElementById("boardsContainer"),
  boardsMessage: document.getElementById("boardsMessage"),
  boardsCount: document.getElementById("boardsCount"),
  boardSearch: document.getElementById("boardSearch"),
};

let allBoards = [];
let progressLookup = { byId: new Map(), byName: new Map() };

function setMessage(text) {
  refs.boardsMessage.textContent = text || "";
}

function formatTimestamp(value) {
  if (!value) return "";
  if (value.includes("T")) return value.replace("T", " ").slice(0, 16);
  return value;
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
    setMessage(keyword ? "검색 결과가 없습니다." : "표시할 빙고판이 없습니다.");
    return;
  }

  setMessage("");
  filtered.forEach((board) => refs.boardsContainer.append(createBoardCard(board)));
}

async function loadBoards() {
  try {
    const [boardsRes, progressRes] = await Promise.all([
      fetch(DATA_URL, { cache: "no-store" }),
      fetch(PROGRESS_URL, { cache: "no-store" }),
    ]);
    if (!boardsRes.ok) throw new Error(`데이터 로드 실패: ${boardsRes.status}`);
    const boardsJson = await boardsRes.json();
    allBoards = Array.isArray(boardsJson.boards) ? boardsJson.boards : [];

    progressLookup = { byId: new Map(), byName: new Map() };
    if (progressRes.ok) {
      const progressJson = await progressRes.json();
      const players = Array.isArray(progressJson.players) ? progressJson.players : [];
      players.forEach((player) => {
        if (player.id) progressLookup.byId.set(player.id, player);
        if (player.name) progressLookup.byName.set(player.name, player);
      });
    }

    renderBoards(refs.boardSearch.value);
  } catch (err) {
    setMessage("boards.json을 불러오지 못했습니다. tools/generate_boards.py 실행 후 다시 시도하세요.");
  }
}

function init() {
  refs.boardSearch.addEventListener("input", (e) => renderBoards(e.target.value));
  loadBoards();
}

document.addEventListener("DOMContentLoaded", init);
