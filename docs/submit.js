const STORAGE_KEYS = {
  apiBase: "mrc_submit_api_base",
  submitKey: "mrc_submit_key",
  playerName: "mrc_submit_player_name",
};
const DEFAULT_API_BASE = "https://payday-congressional-till-exposure.trycloudflare.com";
const DEFAULT_BOARDS_URL = "./data/boards.json";
const DEFAULT_PROGRESS_URL = "./data/progress.json";

const customSelectStates = [];
let customSelectEventsBound = false;

function $(id) {
  return document.getElementById(id);
}

function normalizeBaseUrl(url) {
  const trimmed = (url || "").trim();
  if (!trimmed) return "";
  return trimmed.replace(/\/+$/, "");
}

function getApiBase() {
  const stored = localStorage.getItem(STORAGE_KEYS.apiBase);
  if (stored === null) return normalizeBaseUrl(DEFAULT_API_BASE);
  return normalizeBaseUrl(stored);
}

function getBoardsUrl() {
  const base = getApiBase();
  return base ? `${base}/api/v1/boards` : DEFAULT_BOARDS_URL;
}

function getProgressUrl() {
  const base = getApiBase();
  return base ? `${base}/api/v1/progress` : DEFAULT_PROGRESS_URL;
}

function getAdminBaseOverride() {
  const meta = document.querySelector('meta[name="mrc-admin-base"]');
  if (meta && meta.getAttribute("content")) return meta.getAttribute("content");
  if (window.MRC_ADMIN_BASE) return window.MRC_ADMIN_BASE;
  if (window.MRC_ADMIN_URL) return window.MRC_ADMIN_URL;
  return "";
}

function buildAdminUrl(base) {
  if (!base) return "";
  if (base.startsWith("/")) return base;
  try {
    return new URL("/admin", base).toString().replace(/\/+$/, "");
  } catch {
    return `${normalizeBaseUrl(base)}/admin`;
  }
}

function updateAdminLink() {
  const link = $("adminLink");
  if (!link) return;
  const storedBase = localStorage.getItem(STORAGE_KEYS.apiBase);
  const fallbackBase = storedBase === null ? DEFAULT_API_BASE : storedBase || "";
  const overrideBase = getAdminBaseOverride();
  const adminBase = normalizeBaseUrl(overrideBase || fallbackBase);
  const adminUrl = buildAdminUrl(adminBase);
  if (!adminUrl) {
    link.href = "#";
    link.classList.add("is-disabled");
    link.setAttribute("aria-disabled", "true");
    return;
  }
  link.href = adminUrl;
  link.classList.remove("is-disabled");
  link.setAttribute("aria-disabled", "false");
  link.setAttribute("target", "_blank");
  link.setAttribute("rel", "noopener");
}

function setMessage(el, message, type) {
  el.textContent = message || "";
  if (!message) {
    el.removeAttribute("data-type");
    return;
  }
  el.setAttribute("data-type", type || "info");
}

async function loadJsonWithFallback(primaryUrl, fallbackUrl) {
  try {
    const res = await fetch(primaryUrl, { cache: "no-store" });
    if (!res.ok) throw new Error(`요청 실패: ${res.status}`);
    return { data: await res.json(), fallback: false };
  } catch (err) {
    if (primaryUrl === fallbackUrl) throw err;
    const res = await fetch(fallbackUrl, { cache: "no-store" });
    if (!res.ok) throw new Error(`요청 실패: ${res.status}`);
    return { data: await res.json(), fallback: true };
  }
}

const TIER_ALIASES = {
  beginner: "beginner",
  beg: "beginner",
  b: "beginner",
  "초보": "beginner",
  intermediate: "intermediate",
  inter: "intermediate",
  i: "intermediate",
  "중수": "intermediate",
  advanced: "advanced",
  adv: "advanced",
  a: "advanced",
  "고수": "advanced",
};
let tierIndexPromise = null;

function normalizeTierLabel(value) {
  const raw = (value || "").trim();
  if (!raw) return "";
  if (TIER_ALIASES[raw]) return TIER_ALIASES[raw];
  const lower = raw.toLowerCase();
  return TIER_ALIASES[lower] || "";
}

async function loadTierIndex() {
  if (tierIndexPromise) return tierIndexPromise;
  tierIndexPromise = (async () => {
    const boardsUrl = getBoardsUrl();
    const fallbackBoards = boardsUrl !== DEFAULT_BOARDS_URL ? DEFAULT_BOARDS_URL : boardsUrl;
    const result = await loadJsonWithFallback(boardsUrl, fallbackBoards);
    const boards = Array.isArray(result.data?.boards) ? result.data.boards : [];
    const map = new Map();
    boards.forEach((board) => {
      const name = (board?.name || "").trim();
      const tier = normalizeTierLabel(board?.tier || board?.tier_label || "");
      if (name && tier) map.set(name, tier);
    });
    return map;
  })();
  return tierIndexPromise;
}

function createBoardCell(cell, isChecked) {
  const div = document.createElement("div");
  div.className = "board-cell board-cell--static";
  if (cell.type) div.classList.add(`board-cell--${cell.type}`);
  if (isChecked) div.classList.add("board-cell--checked");

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

function renderBoardPreview(board, checkedCodes) {
  const wrap = $("boardPreview");
  wrap.innerHTML = "";
  if (!board) return;
  board.grid.forEach((row) => {
    row.forEach((cell) => {
      const isChecked = checkedCodes.has(cell.code);
      wrap.appendChild(createBoardCell(cell, isChecked));
    });
  });
}

async function loadBoardPreview() {
  const name = ($("playerName").value || "").trim();
  const status = $("boardStatus");
  if (!name) {
    renderBoardPreview(null, new Set());
    status.textContent = "이름을 입력하면 내 빙고판을 불러올 수 있어요.";
    return;
  }

  const boardsUrl = getBoardsUrl();
  const progressUrl = getProgressUrl();
  const fallbackBoards = boardsUrl !== DEFAULT_BOARDS_URL ? DEFAULT_BOARDS_URL : boardsUrl;
  const fallbackProgress = progressUrl !== DEFAULT_PROGRESS_URL ? DEFAULT_PROGRESS_URL : progressUrl;

  status.textContent = "빙고판 불러오는 중...";
  try {
    const [boardsResult, progressResult] = await Promise.all([
      loadJsonWithFallback(boardsUrl, fallbackBoards),
      loadJsonWithFallback(progressUrl, fallbackProgress),
    ]);
    const boards = Array.isArray(boardsResult.data?.boards) ? boardsResult.data.boards : [];
    const players = Array.isArray(progressResult.data?.players) ? progressResult.data.players : [];
    const board = boards.find((item) => item?.name === name);
    if (!board) {
      renderBoardPreview(null, new Set());
      status.textContent = "이름에 해당하는 빙고판이 없습니다.";
      return;
    }

    const progress =
      players.find((item) => item?.id && item.id === board.player_id) ||
      players.find((item) => item?.name === name);
    const checkedCodes = new Set(progress?.checked_codes || []);
    renderBoardPreview(board, checkedCodes);
    const countText = checkedCodes.size ? `진행도 ${checkedCodes.size}/25` : "아직 체크된 칸이 없습니다.";
    const fallbackNote =
      boardsResult.fallback || progressResult.fallback ? " · 서버 연결 불가: 예시 데이터" : "";
    status.textContent = `${countText}${fallbackNote}`;
  } catch (err) {
    renderBoardPreview(null, new Set());
    status.textContent = err?.message || "빙고판 정보를 불러오지 못했습니다.";
  }
}

function collectClaimLabels() {
  const inputs = Array.from(document.querySelectorAll(".claim-input"));
  return inputs
    .map((input) => normalizeLabel(input.value))
    .filter((v) => v.length > 0);
}

function normalizeLabel(value) {
  const raw = (value || "").trim().toUpperCase().replace(/\s+/g, "");
  if (!raw) return "";
  const match = raw.match(/^([ABCDW])(\d{1,2})$/);
  if (!match) return raw;
  return `${match[1]}${match[2].padStart(2, "0")}`;
}

function previewRules(labels, options = {}) {
  const labelPattern = /^[ABCDW]\d{2}$/;
  const allowEmpty = options.allowEmpty || false;
  const counts = { A: 0, B: 0, C: 0, D: 0, W: 0, "?": 0 };
  const invalid = new Set();
  labels.forEach((label) => {
    if (!labelPattern.test(label)) {
      invalid.add(label);
      counts["?"] += 1;
      return;
    }
    const t = label[0] || "?";
    if (counts[t] == null) counts["?"] += 1;
    else counts[t] += 1;
  });

  const warnings = [];
  if (labels.length === 0 && !allowEmpty) warnings.push("카드 코드(라벨)를 1개 이상 입력하세요.");
  if (invalid.size > 0) warnings.push(`카드 코드 형식이 이상해요: ${Array.from(invalid).join(", ")}`);
  if (labels.length > 2) warnings.push("러닝 1회당 최대 2칸까지만 가능해요.");
  if (counts.A > 1) warnings.push("A는 1회당 최대 1칸.");
  if (counts.B > 1) warnings.push("B는 1회당 최대 1칸.");
  if (counts.C > 1) warnings.push("C는 1회당 최대 1칸.");

  const summary = `선택: ${labels.length}칸 (A${counts.A}/B${counts.B}/C${counts.C}/D${counts.D}/W${counts.W})`;
  return { summary, warnings };
}

async function testConnection(apiBase, submitKey) {
  const url = `${apiBase}/healthz`;
  const res = await fetch(url, {
    method: "GET",
    headers: submitKey ? { "X-MRC-Submit-Key": submitKey } : undefined,
  });
  if (!res.ok) throw new Error(`서버 응답 실패: ${res.status}`);
  const json = await res.json();
  if (!json || json.status !== "ok") throw new Error("서버 응답이 올바르지 않습니다.");
}

function saveConn() {
  const apiBase = normalizeBaseUrl($("apiBase").value);
  const submitKey = ($("submitKey").value || "").trim();
  localStorage.setItem(STORAGE_KEYS.apiBase, apiBase);
  localStorage.setItem(STORAGE_KEYS.submitKey, submitKey);
  updateAdminLink();
  return { apiBase, submitKey };
}

function loadConn() {
  const storedBase = localStorage.getItem(STORAGE_KEYS.apiBase);
  $("apiBase").value = storedBase === null ? DEFAULT_API_BASE : storedBase;
  $("submitKey").value = localStorage.getItem(STORAGE_KEYS.submitKey) || "";
  $("playerName").value = localStorage.getItem(STORAGE_KEYS.playerName) || "";
  updateAdminLink();
}

function savePlayerFields() {
  localStorage.setItem(STORAGE_KEYS.playerName, $("playerName").value || "");
}

function renderRulePreview() {
  const labels = collectClaimLabels();
  const tokenEvent = ($("tokenEvent")?.value || "").trim();
  const allowEmpty = tokenEvent === "seal" || tokenEvent === "shield";
  const { summary, warnings } = previewRules(labels, { allowEmpty });
  const el = $("rulePreview");
  if (!el) return;
  if (warnings.length > 0) {
    el.textContent = `${summary} · ${warnings.join(" ")}`;
  } else {
    el.textContent = `${summary} · OK`;
  }
}

function updateTokenFields() {
  const eventValue = ($("tokenEvent").value || "").trim();
  const showSeal = eventValue === "seal";
  $("sealTargetField").classList.toggle("is-hidden", !showSeal);
  $("sealTypeField").classList.toggle("is-hidden", !showSeal);
  const isTokenOnly = eventValue === "seal" || eventValue === "shield";
  const filesInput = $("files");
  if (filesInput) filesInput.required = !isTokenOnly;
  const runFields = $("runFields");
  if (runFields) {
    runFields.classList.toggle("is-hidden", isTokenOnly);
    runFields.querySelectorAll("input, select, textarea").forEach((el) => {
      el.disabled = isTokenOnly;
    });
  }
  renderRulePreview();
}

function renderResult(result) {
  const list = $("resultList");
  list.innerHTML = "";
  if (!result || !Array.isArray(result.validation)) return;

  result.validation.forEach((item) => {
    const li = document.createElement("li");
    const status = item.status;
    const statusText =
      status === "passed" ? "PASS" : status === "failed" ? "FAIL" : "REVIEW";
    const code = item.resolved_code || item.label || "-";
    li.textContent = `${statusText} · ${code} (${item.type || "?"}, ★${item.stars ?? "?"})${
      item.reasons?.length ? " · " + item.reasons.join(" / ") : ""
    }`;
    li.className = status === "passed" ? "status-ok" : status === "failed" ? "status-bad" : "status-warn";
    list.appendChild(li);
  });
}

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

async function handleSubmit(evt) {
  evt.preventDefault();
  savePlayerFields();

  const apiBase = normalizeBaseUrl(localStorage.getItem(STORAGE_KEYS.apiBase) || "");
  const submitKey = (localStorage.getItem(STORAGE_KEYS.submitKey) || "").trim();
  const tokenEvent = ($("tokenEvent")?.value || "").trim();

  if (!apiBase) {
    setMessage($("submitMessage"), "먼저 ‘서버 연결’에서 제출 서버 주소를 저장하세요.", "error");
    return;
  }

  const labels = collectClaimLabels();
  const allowEmpty = tokenEvent === "seal" || tokenEvent === "shield";
  const { warnings } = previewRules(labels, { allowEmpty });
  if (warnings.length > 0) {
    setMessage($("submitMessage"), warnings.join(" ") + " (자동 판정은 참고용)", "error");
    return;
  }

  const fileInput = $("files");
  const tokenOnly = allowEmpty && labels.length === 0;
  if (!tokenOnly && (!fileInput.files || fileInput.files.length === 0)) {
    setMessage($("submitMessage"), "스크린샷 파일을 1개 이상 첨부하세요.", "error");
    return;
  }

  const form = $("submitForm");
  const fd = new FormData(form);

  // normalize labels to A01/B02 format
  fd.delete("claimed_labels");
  labels.forEach((label) => fd.append("claimed_labels", label));

  // send key as form field (simple request, no extra preflight)
  if (submitKey) fd.append("submit_key", submitKey);

  const groupNamesText = ($("groupNames")?.value || "").trim();
  if (groupNamesText) {
    const names = groupNamesText
      .split(",")
      .map((name) => name.trim())
      .filter(Boolean);
    if (names.length > 0) {
      let tierIndex;
      try {
        tierIndex = await loadTierIndex();
      } catch (err) {
        setMessage($("submitMessage"), err?.message || "티어 정보를 불러오지 못했습니다.", "error");
        return;
      }
      if (!tierIndex || tierIndex.size === 0) {
        setMessage($("submitMessage"), "티어 데이터가 없어 이름으로 자동 입력할 수 없습니다.", "error");
        return;
      }
      const tiers = [];
      const missing = [];
      names.forEach((name) => {
        const tier = tierIndex.get(name);
        if (tier) tiers.push(tier);
        else missing.push(name);
      });
      const selfName = ($("playerName")?.value || "").trim();
      if (selfName) {
        const selfTier = tierIndex.get(selfName);
        if (selfTier) tiers.push(selfTier);
      }
      if (missing.length) {
        setMessage($("submitMessage"), `티어를 찾지 못한 이름: ${missing.join(", ")}`, "error");
        return;
      }
      const uniqueTiers = Array.from(new Set(tiers));
      if (uniqueTiers.length) {
        fd.delete("group_tiers");
        uniqueTiers.forEach((tier) => fd.append("group_tiers", tier));
      }
    }
  }

  $("submitBtn").disabled = true;
  $("submitStatus").textContent = "전송 중…";
  setMessage($("submitMessage"), "", "info");

  try {
    const res = await fetch(`${apiBase}/api/v1/submissions`, {
      method: "POST",
      body: fd,
    });
    const text = await res.text();
    let json;
    try {
      json = JSON.parse(text);
    } catch {
      throw new Error(text || `서버 응답 파싱 실패 (${res.status})`);
    }

    if (!res.ok) {
      const detail = json?.detail;
      if (detail?.messages) throw new Error(detail.messages.join(" "));
      throw new Error(detail || `제출 실패 (${res.status})`);
    }

    $("submitStatus").textContent = `완료 · ID ${json.id}`;
    setMessage($("submitMessage"), "제출이 저장되었습니다. 자동 판정은 참고용이며 운영진 확인 후 확정됩니다.", "success");
    renderResult(json);
  } catch (err) {
    $("submitStatus").textContent = "실패";
    setMessage($("submitMessage"), err?.message || String(err), "error");
  } finally {
    $("submitBtn").disabled = false;
  }
}

async function handleSaveConn() {
  const { apiBase, submitKey } = saveConn();
  if (!apiBase) {
    setMessage($("connStatus"), "제출 서버 주소를 입력하세요.", "error");
    return;
  }
  $("saveConnBtn").disabled = true;
  setMessage($("connStatus"), "연결 확인 중…", "info");
  try {
    await testConnection(apiBase, submitKey);
    setMessage($("connStatus"), "연결 성공", "success");
    loadBoardPreview();
  } catch (err) {
    setMessage($("connStatus"), err?.message || String(err), "error");
  } finally {
    $("saveConnBtn").disabled = false;
  }
}

function init() {
  loadConn();
  initCustomSelects();
  renderRulePreview();
  $("saveConnBtn").addEventListener("click", handleSaveConn);
  $("apiBase").addEventListener("input", updateAdminLink);
  $("submitForm").addEventListener("submit", handleSubmit);
  $("playerName").addEventListener("input", savePlayerFields);
  $("playerName").addEventListener("change", loadBoardPreview);
  $("tokenEvent").addEventListener("change", updateTokenFields);
  $("loadBoardBtn").addEventListener("click", loadBoardPreview);
  document.querySelectorAll(".claim-input").forEach((el) => el.addEventListener("input", renderRulePreview));
  updateTokenFields();
  loadBoardPreview();
}

document.addEventListener("DOMContentLoaded", init);
