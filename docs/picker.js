const SEASON_SEED = "2025W";
const FORM_ACTION =
  "https://docs.google.com/forms/d/e/1FAIpQLSeB4Ig3egZquyy6NiOrNfWhj7e7NTpUJy0EBHdOaeZT2FSQRA/formResponse";
const FORM_NAME_ENTRY = "entry.233447481";
const FORM_CELL_MAP = [
  { row: 0, col: 0, entry: "entry.1425779500" },
  { row: 0, col: 1, entry: "entry.588661901" },
  { row: 0, col: 2, entry: "entry.355020899" },
  { row: 0, col: 3, entry: "entry.589544293" },
  // { row: 0, col: 3, entry: "entry.61302612" },
  { row: 0, col: 4, entry: "entry.2009024998" },
  { row: 1, col: 0, entry: "entry.365601987" },
  { row: 1, col: 1, entry: "entry.657292462" },
  { row: 1, col: 2, entry: "entry.1643315713" },
  { row: 1, col: 3, entry: "entry.1711959780" },
  { row: 1, col: 4, entry: "entry.1040618603" },
  { row: 2, col: 0, entry: "entry.1909607711" },
  { row: 2, col: 1, entry: "entry.680058750" },
  { row: 2, col: 2, entry: "entry.1897556974" },
  { row: 2, col: 3, entry: "entry.986494045" },
  { row: 2, col: 4, entry: "entry.873085168" },
  { row: 3, col: 0, entry: "entry.1864523592" },
  { row: 3, col: 1, entry: "entry.644369121" },
  { row: 3, col: 2, entry: "entry.1307687002" },
  { row: 3, col: 3, entry: "entry.1022767143" },
  { row: 3, col: 4, entry: "entry.956996607" },
  { row: 4, col: 0, entry: "entry.765928249" },
  { row: 4, col: 1, entry: "entry.251435500" },
  { row: 4, col: 2, entry: "entry.356676182" },
  { row: 4, col: 3, entry: "entry.1329417157" },
  { row: 4, col: 4, entry: "entry.333071138" },
];

const CARD_DEFS = [
  { id: "A01", type: "A", stars: 1 },
  { id: "A02", type: "A", stars: 2 },
  { id: "A03", type: "A", stars: 2 },
  { id: "A04", type: "A", stars: 1 },
  { id: "A05", type: "A", stars: 2 },
  { id: "A06", type: "A", stars: 1 },
  { id: "A07", type: "A", stars: 1 },
  { id: "A08", type: "A", stars: 1 },
  { id: "A09", type: "A", stars: 2 },
  { id: "A10", type: "A", stars: 2 },
  { id: "A11", type: "A", stars: 2 },
  { id: "A12", type: "A", stars: 2 },
  { id: "A13", type: "A", stars: 2 },
  { id: "A14", type: "A", stars: 1 },
  { id: "B01", type: "B", stars: 1 },
  { id: "B02", type: "B", stars: 2 },
  { id: "B03", type: "B", stars: 2 },
  { id: "B04", type: "B", stars: 2 },
  { id: "B05", type: "B", stars: 1 },
  { id: "B06", type: "B", stars: 2 },
  { id: "B07", type: "B", stars: 2 },
  { id: "B08", type: "B", stars: 1 },
  { id: "B09", type: "B", stars: 1 },
  { id: "B10", type: "B", stars: 1 },
  { id: "C01", type: "C", stars: 1 },
  { id: "C02", type: "C", stars: 2 },
  { id: "C03", type: "C", stars: 1 },
  { id: "C04", type: "C", stars: 2 },
  { id: "C05", type: "C", stars: 1 },
  { id: "C06", type: "C", stars: 2 },
  { id: "C07", type: "C", stars: 2 },
  { id: "C08", type: "C", stars: 1 },
  { id: "C09", type: "C", stars: 1 },
  { id: "D01", type: "D", stars: 3 },
  { id: "D02", type: "D", stars: 3 },
  { id: "D03", type: "D", stars: 3 },
  { id: "D04", type: "D", stars: 3 },
  { id: "D05", type: "D", stars: 3 },
  { id: "W01", type: "W", stars: 3 },
  { id: "W02", type: "W", stars: 3 },
  { id: "W03", type: "W", stars: 3 },
  { id: "W04", type: "W", stars: 3 },
];

const TYPE_LABELS = {
  A: "Base",
  B: "Condition",
  C: "Co-op",
  D: "Marathon",
  W: "Wild",
};

const BASE_COUNTS = { A: 10, B: 7, C: 5, D: 2, W: 1 };
const VARIANT_COUNTS = {
  intermediate: { A: 10, B: 7, C: 5, D: 1, W: 2 },
  advanced: { A: 9, B: 6, C: 5, D: 2, W: 3 },
};

const corners = [0, 4, 20, 24];
const centerIndex = 12;

const state = {
  tier: "beginner",
  variantW: true,
  cards: [],
  cardsById: {},
  selectedIds: new Set(),
  placements: Array(25).fill(null),
  activeCardId: null,
};

const refs = {
  tierSelect: document.getElementById("tierSelect"),
  variantToggle: document.getElementById("variantToggle"),
  cardGrid: document.getElementById("cardGrid"),
  selectedCards: document.getElementById("selectedCards"),
  boardGrid: document.getElementById("boardGrid"),
  countSummary: document.getElementById("countSummary"),
  ruleStatus: document.getElementById("ruleStatus"),
  messageBox: document.getElementById("messageBox"),
  activeCardLabel: document.getElementById("activeCardLabel"),
  boardPreview: document.getElementById("boardPreview"),
  submitStatus: document.getElementById("submitStatus"),
  playerName: document.getElementById("playerName"),
  autoSelectBtn: document.getElementById("autoSelectBtn"),
  autoAllBtn: document.getElementById("autoAllBtn"),
  autoPlaceBtn: document.getElementById("autoPlaceBtn"),
  clearBoardBtn: document.getElementById("clearBoardBtn"),
  submitBtn: document.getElementById("submitBtn"),
  copyBtn: document.getElementById("copyBtn"),
};

const customSelectStates = [];
let customSelectEventsBound = false;

function syncCustomSelect(state) {
  const selectedIndex = state.select.selectedIndex >= 0 ? state.select.selectedIndex : 0;
  const selectedOption = state.select.options[selectedIndex];
  state.selectedIndex = selectedIndex;
  state.label.textContent = selectedOption ? selectedOption.textContent : "선택";
  state.options.forEach((opt, idx) => {
    const isSelected = idx === selectedIndex;
    opt.button.setAttribute("aria-selected", isSelected ? "true" : "false");
    opt.button.classList.toggle("is-selected", isSelected);
    if (!opt.disabled) opt.button.tabIndex = isSelected ? 0 : -1;
  });
  state.button.disabled = !!state.select.disabled;
}

function closeCustomSelect(state) {
  if (!state.open) return;
  state.open = false;
  state.wrapper.classList.remove("is-open");
  const card = state.wrapper.closest(".card");
  if (card) card.classList.remove("is-elevated");
  state.button.setAttribute("aria-expanded", "false");
}

function openCustomSelect(state, focusSelected) {
  if (state.open) return;
  customSelectStates.forEach((item) => {
    if (item !== state) closeCustomSelect(item);
  });
  state.open = true;
  state.wrapper.classList.add("is-open");
  const card = state.wrapper.closest(".card");
  if (card) card.classList.add("is-elevated");
  state.button.setAttribute("aria-expanded", "true");
  if (focusSelected) {
    const target = state.options[state.selectedIndex];
    if (target && !target.disabled) {
      requestAnimationFrame(() => target.button.focus());
    }
  }
}

function toggleCustomSelect(state, focusSelected) {
  if (state.open) closeCustomSelect(state);
  else openCustomSelect(state, focusSelected);
}

function findNextOption(state, startIndex, direction) {
  const total = state.options.length;
  for (let offset = 1; offset <= total; offset += 1) {
    const idx = (startIndex + direction * offset + total) % total;
    if (!state.options[idx].disabled) return idx;
  }
  return startIndex;
}

function selectCustomOption(state, idx) {
  const option = state.options[idx];
  if (!option || option.disabled) return;
  state.select.value = option.value;
  state.select.dispatchEvent(new Event("change", { bubbles: true }));
  syncCustomSelect(state);
  closeCustomSelect(state);
  state.button.focus();
}

function buildCustomSelect(select) {
  if (select.dataset.customReady === "true") return null;
  select.dataset.customReady = "true";

  const wrapper = document.createElement("div");
  wrapper.className = "custom-select";

  const button = document.createElement("button");
  button.type = "button";
  button.className = "custom-select__button";
  button.setAttribute("aria-haspopup", "listbox");
  button.setAttribute("aria-expanded", "false");

  const labelSpan = document.createElement("span");
  labelSpan.className = "custom-select__label";
  button.appendChild(labelSpan);

  const caret = document.createElement("span");
  caret.className = "custom-select__caret";
  button.appendChild(caret);

  const list = document.createElement("div");
  list.className = "custom-select__list";
  list.setAttribute("role", "listbox");

  const fallbackId = `custom-select-${customSelectStates.length + 1}`;
  const baseId = select.id || fallbackId;
  const listId = `${baseId}-list`;
  const buttonId = `${baseId}-button`;
  list.id = listId;
  button.id = buttonId;
  button.setAttribute("aria-controls", listId);
  list.setAttribute("aria-labelledby", buttonId);

  select.classList.add("custom-select__native");
  select.tabIndex = -1;
  select.setAttribute("aria-hidden", "true");

  const state = {
    select,
    wrapper,
    button,
    label: labelSpan,
    list,
    options: [],
    selectedIndex: 0,
    open: false,
  };

  Array.from(select.options).forEach((opt, idx) => {
    const optionButton = document.createElement("button");
    optionButton.type = "button";
    optionButton.className = "custom-select__option";
    optionButton.setAttribute("role", "option");
    optionButton.dataset.value = opt.value;
    optionButton.textContent = opt.textContent;
    optionButton.tabIndex = -1;
    if (opt.disabled) {
      optionButton.disabled = true;
      optionButton.classList.add("is-disabled");
    }
    optionButton.addEventListener("click", (event) => {
      event.preventDefault();
      selectCustomOption(state, idx);
    });
    optionButton.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const direction = event.key === "ArrowDown" ? 1 : -1;
        const nextIdx = findNextOption(state, idx, direction);
        state.options[nextIdx].button.focus();
        return;
      }
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectCustomOption(state, idx);
      }
      if (event.key === "Escape") {
        event.preventDefault();
        closeCustomSelect(state);
        state.button.focus();
      }
    });
    state.options.push({
      button: optionButton,
      value: opt.value,
      disabled: opt.disabled,
    });
    list.appendChild(optionButton);
  });

  const field = select.closest(".field");
  const label = field ? field.querySelector(`label[for="${select.id}"]`) : null;
  if (label) {
    if (!label.id) label.id = `${baseId}-label`;
    button.setAttribute("aria-labelledby", label.id);
    label.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      toggleCustomSelect(state, true);
      button.focus();
    });
  } else {
    button.setAttribute("aria-label", select.name || "선택");
  }

  button.addEventListener("click", (event) => {
    event.preventDefault();
    toggleCustomSelect(state, true);
  });
  button.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      openCustomSelect(state, true);
    }
  });

  select.addEventListener("change", () => syncCustomSelect(state));

  select.parentNode.insertBefore(wrapper, select);
  wrapper.appendChild(select);
  wrapper.appendChild(button);
  wrapper.appendChild(list);

  syncCustomSelect(state);
  return state;
}

function initCustomSelects() {
  const selects = Array.from(document.querySelectorAll("select[data-custom-select]"));
  if (selects.length === 0) return;

  selects.forEach((select) => {
    const state = buildCustomSelect(select);
    if (state) customSelectStates.push(state);
  });

  if (customSelectEventsBound) return;
  customSelectEventsBound = true;

  document.addEventListener("click", (event) => {
    if (event.target.closest(".custom-select")) return;
    customSelectStates.forEach((state) => closeCustomSelect(state));
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    customSelectStates.forEach((state) => closeCustomSelect(state));
  });
}

function hashString(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
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

function shuffle(array, rng) {
  for (let i = array.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [array[i], array[j]] = [array[j], array[i]];
  }
  return array;
}

function buildCards(seed) {
  const rng = mulberry32(hashString(seed));
  const cards = CARD_DEFS.map((card) => ({ ...card }));
  const byType = { A: [], B: [], C: [], D: [], W: [] };
  cards.forEach((card) => byType[card.type].push(card));
  Object.keys(byType).forEach((type) => {
    byType[type].sort((a, b) => a.id.localeCompare(b.id));
    const labels = byType[type].map((card) => card.id);
    shuffle(labels, rng);
    byType[type].forEach((card, idx) => {
      card.label = labels[idx];
    });
  });
  return cards;
}

function getRequiredCounts() {
  if (!state.variantW) return { ...BASE_COUNTS };
  if (state.tier === "intermediate") return { ...VARIANT_COUNTS.intermediate };
  if (state.tier === "advanced") return { ...VARIANT_COUNTS.advanced };
  return { ...BASE_COUNTS };
}

function getWMode() {
  if (!state.variantW || state.tier === "beginner") return { count: 1, mode: "center" };
  if (state.tier === "intermediate") return { count: 2, mode: "center+corner" };
  return { count: 3, mode: "center+diagonal" };
}

function formatStars(count) {
  return "★".repeat(count);
}

function formatCard(card) {
  return `${card.label} ${formatStars(card.stars)}`;
}

function getSelectedCards() {
  return Array.from(state.selectedIds).map((id) => state.cardsById[id]);
}

function getSelectedCounts() {
  const counts = { A: 0, B: 0, C: 0, D: 0, W: 0 };
  state.selectedIds.forEach((id) => {
    const card = state.cardsById[id];
    if (card) counts[card.type] += 1;
  });
  return counts;
}

function setMessage(text, type = "info") {
  refs.messageBox.textContent = text;
  refs.messageBox.dataset.type = type;
}

function clearMessage() {
  refs.messageBox.textContent = "";
  refs.messageBox.dataset.type = "";
}

function selectCard(id) {
  const card = state.cardsById[id];
  if (!card) return;
  const required = getRequiredCounts();
  const counts = getSelectedCounts();
  if (counts[card.type] >= required[card.type]) {
    setMessage(`${card.type} 카드는 ${required[card.type]}장까지 선택 가능합니다.`, "error");
    return;
  }
  state.selectedIds.add(id);
  clearMessage();
}

function deselectCard(id) {
  if (!state.selectedIds.has(id)) return;
  state.selectedIds.delete(id);
  removeCardFromBoard(id);
  if (state.activeCardId === id) state.activeCardId = null;
  clearMessage();
}

function toggleCardSelection(id) {
  if (state.selectedIds.has(id)) deselectCard(id);
  else selectCard(id);
  render();
}

function removeCardFromBoard(id) {
  const idx = state.placements.indexOf(id);
  if (idx !== -1) state.placements[idx] = null;
}

function setActiveCard(id) {
  state.activeCardId = id;
  const card = state.cardsById[id];
  refs.activeCardLabel.textContent = card ? formatCard(card) : "없음";
  renderSelectedCards();
  renderBoard();
}

function handleSelectedCardClick(id) {
  if (state.activeCardId === id) {
    state.activeCardId = null;
    refs.activeCardLabel.textContent = "없음";
  } else {
    setActiveCard(id);
  }
  renderSelectedCards();
  renderBoard();
}

function getPlacementIndex(row, col) {
  return row * 5 + col;
}

function getRowCol(idx) {
  return { row: Math.floor(idx / 5), col: idx % 5 };
}

function isCorner(idx) {
  return corners.includes(idx);
}

function getAdjacentIndices(idx) {
  const { row, col } = getRowCol(idx);
  const list = [];
  if (row > 0) list.push(getPlacementIndex(row - 1, col));
  if (row < 4) list.push(getPlacementIndex(row + 1, col));
  if (col > 0) list.push(getPlacementIndex(row, col - 1));
  if (col < 4) list.push(getPlacementIndex(row, col + 1));
  return list;
}

function canPlaceCardAt(cardId, idx) {
  const card = state.cardsById[cardId];
  if (!card) return { ok: false, message: "카드를 찾을 수 없습니다." };
  if (!state.selectedIds.has(cardId)) return { ok: false, message: "선택된 카드만 배치할 수 있습니다." };
  if (card.type === "W") {
    const wMode = getWMode();
    const allowed = wMode.mode === "center" ? [centerIndex] : [centerIndex, ...corners];
    if (!allowed.includes(idx)) return { ok: false, message: "W 카드는 중앙/모서리만 배치 가능합니다." };
    if (wMode.mode === "center+diagonal" && isCorner(idx)) {
      const existingCorners = state.placements
        .map((id, i) => ({ id, i }))
        .filter((slot) => slot.id && state.cardsById[slot.id].type === "W" && isCorner(slot.i))
        .map((slot) => slot.i);
      if (existingCorners.length === 1) {
        const target = existingCorners[0];
        const diagOk =
          (target === 0 && idx === 24) ||
          (target === 24 && idx === 0) ||
          (target === 4 && idx === 20) ||
          (target === 20 && idx === 4);
        if (!diagOk) return { ok: false, message: "고수 W는 대각선 모서리 2개를 배치해야 합니다." };
      }
    }
  }
  if (card.type === "D" && isCorner(idx)) {
    return { ok: false, message: "D 카드는 모서리에 배치할 수 없습니다." };
  }
  if (card.type === "C") {
    const hasAdjacentC = getAdjacentIndices(idx).some((adjIdx) => {
      const adjId = state.placements[adjIdx];
      return adjId && state.cardsById[adjId].type === "C";
    });
    if (hasAdjacentC) return { ok: false, message: "C 카드는 상하좌우 인접 배치가 불가합니다." };
  }
  return { ok: true };
}

function placeCardAt(cardId, idx) {
  const check = canPlaceCardAt(cardId, idx);
  if (!check.ok) {
    setMessage(check.message || "배치할 수 없는 위치입니다.", "error");
    return false;
  }
  clearMessage();
  const existingIdx = state.placements.indexOf(cardId);
  if (existingIdx !== -1) state.placements[existingIdx] = null;
  state.placements[idx] = cardId;
  state.activeCardId = null;
  refs.activeCardLabel.textContent = "없음";
  render();
  return true;
}

function removeCardAt(idx) {
  const existing = state.placements[idx];
  if (!existing) return;
  state.placements[idx] = null;
  render();
}

function handleBoardClick(idx) {
  if (state.activeCardId) {
    placeCardAt(state.activeCardId, idx);
    return;
  }
  removeCardAt(idx);
}

function renderCardGrid() {
  refs.cardGrid.innerHTML = "";
  const required = getRequiredCounts();
  const counts = getSelectedCounts();
  state.cards.forEach((card) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `card-back card-back--${card.type}`;
    btn.dataset.id = card.id;
    btn.setAttribute("aria-pressed", state.selectedIds.has(card.id));
    if (!state.selectedIds.has(card.id) && counts[card.type] >= required[card.type]) {
      btn.classList.add("is-disabled");
    }
    if (state.selectedIds.has(card.id)) btn.classList.add("is-selected");
    btn.innerHTML = `
      <div class="card-back__code">${card.label}</div>
      <div class="card-back__stars">${formatStars(card.stars)}</div>
      <div class="card-back__type">${TYPE_LABELS[card.type]}</div>
    `;
    btn.addEventListener("click", () => {
      if (btn.classList.contains("is-disabled") && !state.selectedIds.has(card.id)) return;
      toggleCardSelection(card.id);
    });
    refs.cardGrid.appendChild(btn);
  });
}

function renderSelectedCards() {
  refs.selectedCards.innerHTML = "";
  const selected = getSelectedCards();
  const unplaced = selected.filter((card) => !state.placements.includes(card.id));
  if (!unplaced.length) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "배치할 카드가 없습니다.";
    refs.selectedCards.appendChild(empty);
    return;
  }
  unplaced.forEach((card) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `card-mini card-mini--${card.type}`;
    if (state.activeCardId === card.id) btn.classList.add("is-active");
    btn.textContent = formatCard(card);
    btn.addEventListener("click", () => handleSelectedCardClick(card.id));
    refs.selectedCards.appendChild(btn);
  });
}

function renderBoard() {
  refs.boardGrid.innerHTML = "";
  for (let idx = 0; idx < 25; idx++) {
    const cell = document.createElement("button");
    cell.type = "button";
    cell.className = "board-cell";
    cell.dataset.idx = String(idx);
    if (state.placements[idx]) {
      const card = state.cardsById[state.placements[idx]];
      cell.classList.add(`board-cell--${card.type}`);
      cell.innerHTML = `
        <span class="cell__code">${card.label}</span>
        <span class="cell__stars">${formatStars(card.stars)}</span>
      `;
    } else {
      cell.innerHTML = `<span class="cell__placeholder">+</span>`;
    }
    if (state.activeCardId) cell.classList.add("board-cell--active");
    cell.addEventListener("click", () => handleBoardClick(idx));
    refs.boardGrid.appendChild(cell);
  }
}

function renderCounts() {
  refs.countSummary.innerHTML = "";
  const required = getRequiredCounts();
  const counts = getSelectedCounts();
  Object.keys(required).forEach((type) => {
    const item = document.createElement("div");
    item.className = `count-item count-item--${type}`;
    item.innerHTML = `
      <span class="count-item__label">${type} ${TYPE_LABELS[type]}</span>
      <strong>${counts[type]} / ${required[type]}</strong>
    `;
    refs.countSummary.appendChild(item);
  });
}

function validateSelection() {
  const required = getRequiredCounts();
  const counts = getSelectedCounts();
  const errors = [];
  Object.keys(required).forEach((type) => {
    if (counts[type] !== required[type]) {
      errors.push(`${type} 카드 ${required[type]}장 필요 (현재 ${counts[type]}장)`);
    }
  });
  return errors;
}

function validateBoard() {
  const errors = [];
  if (state.placements.some((slot) => !slot)) errors.push("빙고판 25칸이 모두 채워지지 않았습니다.");

  const wMode = getWMode();
  const wIndices = state.placements
    .map((id, idx) => (id && state.cardsById[id].type === "W" ? idx : null))
    .filter((idx) => idx !== null);
  if (wIndices.length !== wMode.count) {
    errors.push(`W 카드는 ${wMode.count}장 배치해야 합니다.`);
  }
  if (!wIndices.includes(centerIndex)) errors.push("중앙칸은 W 카드가 필수입니다.");
  const allowedW = wMode.mode === "center" ? [centerIndex] : [centerIndex, ...corners];
  wIndices.forEach((idx) => {
    if (!allowedW.includes(idx)) errors.push("W 카드는 중앙/모서리 위치만 가능합니다.");
  });
  if (wMode.mode === "center+corner") {
    const cornerCount = wIndices.filter((idx) => isCorner(idx)).length;
    if (cornerCount !== 1) errors.push("중수 W는 모서리 1곳만 배치해야 합니다.");
  }
  if (wMode.mode === "center+diagonal") {
    const cornersPlaced = wIndices.filter((idx) => isCorner(idx));
    if (cornersPlaced.length !== 2) {
      errors.push("고수 W는 모서리 2곳(대각선)을 배치해야 합니다.");
    } else {
      const diagOk =
        (cornersPlaced.includes(0) && cornersPlaced.includes(24)) ||
        (cornersPlaced.includes(4) && cornersPlaced.includes(20));
      if (!diagOk) errors.push("고수 W는 대각선 모서리 2곳을 배치해야 합니다.");
    }
  }

  state.placements.forEach((id, idx) => {
    if (!id) return;
    const card = state.cardsById[id];
    if (card.type === "D" && isCorner(idx)) errors.push("D 카드는 모서리에 배치할 수 없습니다.");
  });

  for (let idx = 0; idx < 25; idx++) {
    const id = state.placements[idx];
    if (!id) continue;
    const card = state.cardsById[id];
    if (card.type !== "C") continue;
    const hasAdjacentC = getAdjacentIndices(idx).some((adjIdx) => {
      const adjId = state.placements[adjIdx];
      return adjId && state.cardsById[adjId].type === "C";
    });
    if (hasAdjacentC) {
      errors.push("C 카드는 상하좌우 인접 배치가 불가합니다.");
      break;
    }
  }

  return errors;
}

function renderStatus() {
  refs.ruleStatus.innerHTML = "";
  const selectionErrors = validateSelection();
  const boardErrors = validateBoard();
  const allErrors = [...selectionErrors, ...boardErrors];
  if (!allErrors.length) {
    const ok = document.createElement("li");
    ok.className = "status-ok";
    ok.textContent = "모든 규칙 충족 완료! 제출 가능합니다.";
    refs.ruleStatus.appendChild(ok);
    return;
  }
  allErrors.forEach((msg) => {
    const li = document.createElement("li");
    li.textContent = msg;
    refs.ruleStatus.appendChild(li);
  });
}

function renderPreview() {
  const lines = [];
  for (let row = 0; row < 5; row++) {
    const cells = [];
    for (let col = 0; col < 5; col++) {
      const idx = getPlacementIndex(row, col);
      const id = state.placements[idx];
      if (!id) cells.push("____");
      else cells.push(formatCard(state.cardsById[id]));
    }
    lines.push(cells.join(" | "));
  }
  refs.boardPreview.value = lines.join("\n");
}

function render() {
  renderCardGrid();
  renderSelectedCards();
  renderBoard();
  renderCounts();
  renderStatus();
  renderPreview();
}

function autoSelect() {
  const rng = Math.random;
  const required = getRequiredCounts();
  state.selectedIds.clear();
  state.placements = Array(25).fill(null);
  state.activeCardId = null;
  const cardsByType = { A: [], B: [], C: [], D: [], W: [] };
  state.cards.forEach((card) => cardsByType[card.type].push(card));
  Object.keys(cardsByType).forEach((type) => {
    shuffle(cardsByType[type], rng);
    cardsByType[type].slice(0, required[type]).forEach((card) => state.selectedIds.add(card.id));
  });
  clearMessage();
  render();
}

function autoPlace() {
  const selectionErrors = validateSelection();
  if (selectionErrors.length) {
    setMessage("카드 선택 수량을 먼저 맞춰주세요.", "error");
    return;
  }
  const result = generateBoard();
  if (!result) {
    setMessage("자동 배치 실패. 다시 시도해 주세요.", "error");
    return;
  }
  state.placements = result;
  state.activeCardId = null;
  clearMessage();
  render();
}

function generateBoard() {
  const rng = Math.random;
  const selected = getSelectedCards();
  const wMode = getWMode();
  const board = Array(25).fill(null);
  const cardsByType = { A: [], B: [], C: [], D: [], W: [] };
  selected.forEach((card) => cardsByType[card.type].push(card));

  const wPositions = [centerIndex];
  if (wMode.mode === "center+corner") {
    const corner = corners[Math.floor(rng() * corners.length)];
    wPositions.push(corner);
  }
  if (wMode.mode === "center+diagonal") {
    const diag = rng() < 0.5 ? [0, 24] : [4, 20];
    wPositions.push(...diag);
  }
  const wCards = shuffle(cardsByType.W.slice(), rng);
  wPositions.forEach((pos, idx) => {
    if (wCards[idx]) board[pos] = wCards[idx].id;
  });

  const dCards = shuffle(cardsByType.D.slice(), rng);
  const dTargets = board
    .map((v, idx) => (v ? null : idx))
    .filter((idx) => idx !== null && !isCorner(idx));
  shuffle(dTargets, rng);
  dCards.forEach((card, i) => {
    if (dTargets[i] !== undefined) board[dTargets[i]] = card.id;
  });

  let boardWithC = null;
  const cCards = shuffle(cardsByType.C.slice(), rng);
  for (let attempt = 0; attempt < 200; attempt++) {
    const temp = board.slice();
    let ok = true;
    for (const card of cCards) {
      const candidates = temp
        .map((v, idx) => (v ? null : idx))
        .filter((idx) => idx !== null)
        .filter((idx) => !getAdjacentIndices(idx).some((adj) => temp[adj] && state.cardsById[temp[adj]].type === "C"));
      if (!candidates.length) {
        ok = false;
        break;
      }
      const pick = candidates[Math.floor(rng() * candidates.length)];
      temp[pick] = card.id;
    }
    if (ok) {
      boardWithC = temp;
      break;
    }
  }
  if (!boardWithC) return null;

  const remaining = selected.filter((card) => !boardWithC.includes(card.id));
  const emptySlots = boardWithC.map((v, idx) => (v ? null : idx)).filter((idx) => idx !== null);
  shuffle(remaining, rng);
  remaining.forEach((card, i) => {
    if (emptySlots[i] !== undefined) boardWithC[emptySlots[i]] = card.id;
  });

  if (boardWithC.some((slot) => !slot)) return null;
  const errors = validateBoardAgainst(boardWithC);
  if (errors.length) return null;
  return boardWithC;
}

function validateBoardAgainst(placements) {
  const previous = state.placements;
  state.placements = placements;
  const errors = validateBoard();
  state.placements = previous;
  return errors;
}

function handleSubmit() {
  const name = refs.playerName.value.trim();
  if (!name) {
    setMessage("이름을 입력해 주세요.", "error");
    return;
  }
  const selectionErrors = validateSelection();
  const boardErrors = validateBoard();
  if (selectionErrors.length || boardErrors.length) {
    setMessage("규칙 체크를 완료한 후 제출해 주세요.", "error");
    return;
  }

  const payload = new URLSearchParams();
  payload.append(FORM_NAME_ENTRY, name);
  FORM_CELL_MAP.forEach((cell) => {
    const idx = getPlacementIndex(cell.row, cell.col);
    const cardId = state.placements[idx];
    const card = state.cardsById[cardId];
    payload.append(cell.entry, card ? formatCard(card) : "");
  });
  payload.append("fvv", "1");
  payload.append("pageHistory", "0");
  payload.append("fbzx", String(Date.now()));

  refs.submitStatus.textContent = "제출 중...";
  fetch(FORM_ACTION, {
    method: "POST",
    mode: "no-cors",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: payload.toString(),
  })
    .then(() => {
      refs.submitStatus.textContent = "제출 요청 완료!";
      setMessage("응답이 기록되었습니다. (Google Form 기준)", "success");
    })
    .catch(() => {
      refs.submitStatus.textContent = "제출 실패";
      setMessage("제출 실패. 네트워크 상태를 확인해 주세요.", "error");
    });
}

function handleCopy() {
  const text = refs.boardPreview.value;
  if (!text) return;
  navigator.clipboard
    .writeText(text)
    .then(() => setMessage("빙고판 텍스트가 복사되었습니다.", "success"))
    .catch(() => setMessage("복사 실패. 직접 드래그로 복사해 주세요.", "error"));
}

function init() {
  initCustomSelects();
  state.cards = buildCards(SEASON_SEED);
  state.cardsById = Object.fromEntries(state.cards.map((card) => [card.id, card]));

  refs.tierSelect.addEventListener("change", (e) => {
    state.tier = e.target.value;
    render();
  });

  refs.variantToggle.addEventListener("change", (e) => {
    state.variantW = e.target.checked;
    render();
  });

  refs.autoSelectBtn.addEventListener("click", autoSelect);
  refs.autoAllBtn.addEventListener("click", () => {
    autoSelect();
    autoPlace();
  });
  refs.autoPlaceBtn.addEventListener("click", autoPlace);
  refs.clearBoardBtn.addEventListener("click", () => {
    state.placements = Array(25).fill(null);
    state.activeCardId = null;
    render();
  });
  refs.submitBtn.addEventListener("click", handleSubmit);
  refs.copyBtn.addEventListener("click", handleCopy);

  render();
}

init();
