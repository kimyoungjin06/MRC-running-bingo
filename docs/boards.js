const DATA_URL = "./data/boards.json";

const refs = {
  boardsContainer: document.getElementById("boardsContainer"),
  boardsMessage: document.getElementById("boardsMessage"),
  boardsCount: document.getElementById("boardsCount"),
  boardSearch: document.getElementById("boardSearch"),
};

let allBoards = [];

function setMessage(text) {
  refs.boardsMessage.textContent = text || "";
}

function formatTimestamp(value) {
  if (!value) return "";
  if (value.includes("T")) return value.replace("T", " ").slice(0, 16);
  return value;
}

function createCell(cell) {
  const div = document.createElement("div");
  div.className = "board-cell board-cell--static";
  if (cell.type) {
    div.classList.add(`board-cell--${cell.type}`);
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

function createBoardCard(board) {
  const wrap = document.createElement("section");
  wrap.className = "board-card";

  const header = document.createElement("div");
  header.className = "board-card__header";

  const title = document.createElement("div");
  title.className = "board-card__title";
  title.textContent = board.name || "이름 없음";

  const meta = document.createElement("div");
  meta.className = "board-card__meta";
  const ts = formatTimestamp(board.timestamp);
  meta.textContent = ts ? `제출: ${ts}` : "제출 시간 없음";

  header.append(title, meta);

  const grid = document.createElement("div");
  grid.className = "board board--public";
  board.grid.forEach((row) => {
    row.forEach((cell) => grid.append(createCell(cell)));
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
    const res = await fetch(DATA_URL, { cache: "no-store" });
    if (!res.ok) throw new Error(`데이터 로드 실패: ${res.status}`);
    const json = await res.json();
    allBoards = Array.isArray(json.boards) ? json.boards : [];
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
