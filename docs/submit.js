const STORAGE_KEYS = {
  apiBase: "mrc_submit_api_base",
  submitKey: "mrc_submit_key",
  playerName: "mrc_submit_player_name",
  tier: "mrc_submit_tier",
};

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
  const storedBase = localStorage.getItem(STORAGE_KEYS.apiBase) || "";
  const overrideBase = getAdminBaseOverride();
  const adminBase = normalizeBaseUrl(overrideBase || storedBase);
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

function previewRules(labels) {
  const labelPattern = /^[ABCDW]\d{2}$/;
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
  if (labels.length === 0) warnings.push("카드 코드(라벨)를 1개 이상 입력하세요.");
  if (invalid.size > 0) warnings.push(`카드 코드 형식이 이상해요: ${Array.from(invalid).join(", ")}`);
  if (labels.length > 3) warnings.push("러닝 1회당 최대 3칸까지만 가능해요.");
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
  $("apiBase").value = localStorage.getItem(STORAGE_KEYS.apiBase) || "";
  $("submitKey").value = localStorage.getItem(STORAGE_KEYS.submitKey) || "";
  $("playerName").value = localStorage.getItem(STORAGE_KEYS.playerName) || "";
  $("tier").value = localStorage.getItem(STORAGE_KEYS.tier) || "beginner";
  updateAdminLink();
}

function savePlayerFields() {
  localStorage.setItem(STORAGE_KEYS.playerName, $("playerName").value || "");
  localStorage.setItem(STORAGE_KEYS.tier, $("tier").value || "beginner");
}

function renderRulePreview() {
  const labels = collectClaimLabels();
  const { summary, warnings } = previewRules(labels);
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
  state.button.setAttribute("aria-expanded", "false");
}

function openCustomSelect(state, focusSelected) {
  if (state.open) return;
  customSelectStates.forEach((item) => {
    if (item !== state) closeCustomSelect(item);
  });
  state.open = true;
  state.wrapper.classList.add("is-open");
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

  if (!apiBase) {
    setMessage($("submitMessage"), "먼저 ‘서버 연결’에서 제출 서버 주소를 저장하세요.", "error");
    return;
  }

  const labels = collectClaimLabels();
  const { warnings } = previewRules(labels);
  if (warnings.length > 0) {
    setMessage($("submitMessage"), warnings.join(" "), "error");
    return;
  }

  const fileInput = $("files");
  if (!fileInput.files || fileInput.files.length === 0) {
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

  // normalize group_tiers: turn comma text into repeated fields
  const groupTiersText = ($("groupTiers").value || "").trim();
  if (groupTiersText) {
    fd.delete("group_tiers");
    groupTiersText
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean)
      .forEach((t) => fd.append("group_tiers", t));
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
    setMessage($("submitMessage"), "제출이 저장되었습니다. 아래 자동 판정 결과를 확인하세요.", "success");
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
  $("tier").addEventListener("change", savePlayerFields);
  $("tokenEvent").addEventListener("change", updateTokenFields);
  document.querySelectorAll(".claim-input").forEach((el) => el.addEventListener("input", renderRulePreview));
  updateTokenFields();
}

document.addEventListener("DOMContentLoaded", init);
