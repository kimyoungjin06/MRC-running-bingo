const STORAGE_KEYS = {
  apiBase: "mrc_submit_api_base",
  submitKey: "mrc_submit_key",
  playerName: "mrc_submit_player_name",
  tier: "mrc_submit_tier",
};

function $(id) {
  return document.getElementById(id);
}

function normalizeBaseUrl(url) {
  const trimmed = (url || "").trim();
  if (!trimmed) return "";
  return trimmed.replace(/\/+$/, "");
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
    .map((input) => (input.value || "").trim().toUpperCase())
    .filter((v) => v.length > 0);
}

function previewRules(labels) {
  const labelPattern = /^[ABCDW]\\d{2}$/;
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
  return { apiBase, submitKey };
}

function loadConn() {
  $("apiBase").value = localStorage.getItem(STORAGE_KEYS.apiBase) || "";
  $("submitKey").value = localStorage.getItem(STORAGE_KEYS.submitKey) || "";
  $("playerName").value = localStorage.getItem(STORAGE_KEYS.playerName) || "";
  $("tier").value = localStorage.getItem(STORAGE_KEYS.tier) || "beginner";
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
    li.textContent = `${statusText} · ${item.label} → ${item.resolved_code} (${item.type || "?"}, ★${
      item.stars ?? "?"
    })${item.reasons?.length ? " · " + item.reasons.join(" / ") : ""}`;
    li.className = status === "passed" ? "status-ok" : status === "failed" ? "status-bad" : "status-warn";
    list.appendChild(li);
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
  renderRulePreview();
  $("saveConnBtn").addEventListener("click", handleSaveConn);
  $("submitForm").addEventListener("submit", handleSubmit);
  $("playerName").addEventListener("input", savePlayerFields);
  $("tier").addEventListener("change", savePlayerFields);
  $("tokenEvent").addEventListener("change", updateTokenFields);
  document.querySelectorAll(".claim-input").forEach((el) => el.addEventListener("input", renderRulePreview));
  updateTokenFields();
}

document.addEventListener("DOMContentLoaded", init);
