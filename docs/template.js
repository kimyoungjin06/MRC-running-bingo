const CANVAS_SIZE = { width: 1080, height: 1350 };

const tierLabels = {
  beginner: "초보",
  intermediate: "중수",
  advanced: "고수",
};

const palette = {
  text: "rgba(255, 255, 255, 0.94)",
  muted: "rgba(255, 255, 255, 0.7)",
  accent: "#fbbf24",
  accentSoft: "rgba(251, 191, 36, 0.28)",
  card: "rgba(15, 23, 42, 0.8)",
  stroke: "rgba(255, 255, 255, 0.2)",
};

const defaults = {
  name: "홍길동",
  tier: "beginner",
  date: "",
  summary: "6.2km · 42분",
  boardId: "BINGGO-0001",
  note: "오늘의 한 줄을 적어주세요.",
  placeholder: true,
};

const refs = {
  name: document.getElementById("tplName"),
  tier: document.getElementById("tplTier"),
  date: document.getElementById("tplDate"),
  summary: document.getElementById("tplSummary"),
  boardId: document.getElementById("tplBoardId"),
  note: document.getElementById("tplNote"),
  placeholder: document.getElementById("tplPlaceholder"),
  downloadBtn: document.getElementById("downloadBtn"),
  resetBtn: document.getElementById("resetBtn"),
  status: document.getElementById("templateStatus"),
  canvas: document.getElementById("templateCanvas"),
};

const ctx = refs.canvas.getContext("2d");
const images = {
  bg: null,
  logo: null,
};

function setStatus(message) {
  refs.status.textContent = message || "";
}

function formatDate(value) {
  const dateValue = value || new Date().toISOString().slice(0, 10);
  return dateValue.replace(/-/g, ".");
}

function getValue(input, fallback) {
  return (input.value || "").trim() || fallback;
}

function drawCover(img, x, y, w, h) {
  const scale = Math.max(w / img.width, h / img.height);
  const iw = img.width * scale;
  const ih = img.height * scale;
  const ix = x + (w - iw) / 2;
  const iy = y + (h - ih) / 2;
  ctx.drawImage(img, ix, iy, iw, ih);
}

function roundRect(x, y, w, h, r) {
  const radius = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.arcTo(x + w, y, x + w, y + h, radius);
  ctx.arcTo(x + w, y + h, x, y + h, radius);
  ctx.arcTo(x, y + h, x, y, radius);
  ctx.arcTo(x, y, x + w, y, radius);
  ctx.closePath();
}

function truncateText(text, maxWidth) {
  if (ctx.measureText(text).width <= maxWidth) return text;
  let trimmed = text;
  while (trimmed.length > 0 && ctx.measureText(trimmed + "…").width > maxWidth) {
    trimmed = trimmed.slice(0, -1);
  }
  return trimmed ? trimmed + "…" : "";
}

function wrapText(text, maxWidth) {
  const chars = Array.from(text);
  const lines = [];
  let line = "";
  chars.forEach((char) => {
    const testLine = line + char;
    if (ctx.measureText(testLine).width > maxWidth && line) {
      lines.push(line);
      line = char;
    } else {
      line = testLine;
    }
  });
  if (line) lines.push(line);
  return lines;
}

function drawTextBlock(text, x, y, maxWidth, lineHeight, maxLines = 1) {
  if (!text) return;
  if (maxLines <= 1) {
    ctx.fillText(truncateText(text, maxWidth), x, y);
    return;
  }
  const lines = wrapText(text, maxWidth);
  const finalLines = lines.slice(0, maxLines);
  finalLines.forEach((line, index) => {
    const isLast = index === maxLines - 1 && lines.length > maxLines;
    const content = isLast ? truncateText(line, maxWidth) : line;
    ctx.fillText(content, x, y + lineHeight * index);
  });
}

function drawField(label, value, x, y, width, options = {}) {
  const labelSize = options.labelSize || 18;
  const valueSize = options.valueSize || 30;
  const lineHeight = options.lineHeight || valueSize + 4;
  const maxLines = options.maxLines || 1;

  ctx.font = `600 ${labelSize}px "Segoe UI", system-ui, sans-serif`;
  ctx.fillStyle = palette.muted;
  ctx.fillText(label, x, y);

  ctx.font = `600 ${valueSize}px "Segoe UI", system-ui, sans-serif`;
  ctx.fillStyle = palette.text;
  drawTextBlock(value, x, y + labelSize + 10, width, lineHeight, maxLines);
}

function drawPlaceholderArea(x, y, w, h) {
  ctx.save();
  ctx.strokeStyle = "rgba(255, 255, 255, 0.45)";
  ctx.lineWidth = 3;
  ctx.setLineDash([18, 10]);
  roundRect(x, y, w, h, 22);
  ctx.stroke();
  ctx.restore();

  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = "rgba(255, 255, 255, 0.75)";
  ctx.font = '700 32px "Segoe UI", system-ui, sans-serif';
  ctx.fillText("러닝 기록 캡처", x + w / 2, y + h / 2 - 16);
  ctx.font = '500 22px "Segoe UI", system-ui, sans-serif';
  ctx.fillText("이 영역에 스크린샷을 붙여주세요", x + w / 2, y + h / 2 + 18);
  ctx.textAlign = "left";
  ctx.textBaseline = "alphabetic";
}

function drawTemplate() {
  if (!images.bg || !images.logo) return;

  const width = CANVAS_SIZE.width;
  const height = CANVAS_SIZE.height;
  refs.canvas.width = width;
  refs.canvas.height = height;

  ctx.clearRect(0, 0, width, height);

  drawCover(images.bg, 0, 0, width, height);

  const overlay = ctx.createLinearGradient(0, 0, 0, height);
  overlay.addColorStop(0, "rgba(11, 16, 32, 0.25)");
  overlay.addColorStop(0.55, "rgba(11, 16, 32, 0.62)");
  overlay.addColorStop(1, "rgba(11, 16, 32, 0.82)");
  ctx.fillStyle = overlay;
  ctx.fillRect(0, 0, width, height);

  const glow = ctx.createRadialGradient(width * 0.15, 0, 0, width * 0.15, 0, width);
  glow.addColorStop(0, "rgba(251, 191, 36, 0.28)");
  glow.addColorStop(1, "rgba(251, 191, 36, 0)");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, width, height);

  const logoWidth = 220;
  const logoHeight = (logoWidth / images.logo.width) * images.logo.height;
  const logoX = (width - logoWidth) / 2;
  const logoY = 62;
  ctx.drawImage(images.logo, logoX, logoY, logoWidth, logoHeight);

  ctx.textAlign = "center";
  ctx.fillStyle = palette.text;
  ctx.font = '700 44px "Segoe UI", system-ui, sans-serif';
  ctx.fillText("퍼즐형 빙고 러닝 인증", width / 2, logoY + logoHeight + 46);
  ctx.font = '500 22px "Segoe UI", system-ui, sans-serif';
  ctx.fillStyle = palette.muted;
  ctx.fillText("MRC Binggo 2025W · Personal Proof Template", width / 2, logoY + logoHeight + 80);

  ctx.textAlign = "left";
  const shotX = 90;
  const shotY = 270;
  const shotW = width - 180;
  const shotH = 620;
  if (refs.placeholder.checked) {
    drawPlaceholderArea(shotX, shotY, shotW, shotH);
  } else {
    ctx.save();
    ctx.strokeStyle = "rgba(255, 255, 255, 0.16)";
    ctx.lineWidth = 2;
    roundRect(shotX, shotY, shotW, shotH, 22);
    ctx.stroke();
    ctx.restore();
  }

  const infoX = 90;
  const infoY = shotY + shotH + 36;
  const infoW = shotW;
  const infoH = height - infoY - 80;

  ctx.save();
  roundRect(infoX, infoY, infoW, infoH, 28);
  ctx.fillStyle = palette.card;
  ctx.fill();
  ctx.restore();

  ctx.save();
  roundRect(infoX, infoY, infoW, infoH, 28);
  ctx.strokeStyle = palette.stroke;
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.restore();

  const padding = 42;
  const colGap = 40;
  const columnWidth = (infoW - padding * 2 - colGap) / 2;
  const rowGap = (infoH - padding * 2) / 3;
  const leftX = infoX + padding;
  const rightX = leftX + columnWidth + colGap;
  const rowY1 = infoY + padding + 10;

  const name = getValue(refs.name, defaults.name);
  const tierValue = tierLabels[refs.tier.value] || tierLabels[defaults.tier];
  const dateValue = formatDate(refs.date.value || defaults.date);
  const summary = getValue(refs.summary, defaults.summary);
  const boardId = getValue(refs.boardId, defaults.boardId);
  const note = getValue(refs.note, defaults.note);

  drawField("이름", name, leftX, rowY1, columnWidth);
  drawField("티어", tierValue, rightX, rowY1, columnWidth);

  drawField("날짜", dateValue, leftX, rowY1 + rowGap, columnWidth, { valueSize: 28 });
  drawField("러닝 요약", summary, rightX, rowY1 + rowGap, columnWidth, { valueSize: 28 });

  drawField("빙고판 ID", boardId, leftX, rowY1 + rowGap * 2, columnWidth, { valueSize: 26 });
  drawField("한 줄 기록", note, rightX, rowY1 + rowGap * 2, columnWidth, {
    valueSize: 24,
    lineHeight: 30,
    maxLines: 2,
  });

  ctx.textAlign = "right";
  ctx.font = '500 18px "Segoe UI", system-ui, sans-serif';
  ctx.fillStyle = "rgba(255, 255, 255, 0.55)";
  ctx.fillText("MRC Binggo 2025W", width - 90, height - 42);
  ctx.textAlign = "left";
}

function updateTemplate() {
  drawTemplate();
}

function downloadTemplate() {
  try {
    const dateStamp = formatDate(refs.date.value).replace(/\./g, "");
    const filename = `mrc_binggo_template_${dateStamp}.png`;
    const link = document.createElement("a");
    link.href = refs.canvas.toDataURL("image/png");
    link.download = filename;
    link.click();
    setStatus("PNG가 다운로드되었습니다.");
  } catch (err) {
    setStatus("PNG 생성에 실패했습니다.");
  }
}

function applyDefaults() {
  refs.name.value = defaults.name;
  refs.tier.value = defaults.tier;
  refs.summary.value = defaults.summary;
  refs.boardId.value = defaults.boardId;
  refs.note.value = defaults.note;
  refs.placeholder.checked = defaults.placeholder;
  refs.date.value = new Date().toISOString().slice(0, 10);
}

function bindInputs() {
  const inputs = [
    refs.name,
    refs.tier,
    refs.date,
    refs.summary,
    refs.boardId,
    refs.note,
    refs.placeholder,
  ];
  inputs.forEach((input) => {
    input.addEventListener("input", updateTemplate);
    input.addEventListener("change", updateTemplate);
  });
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.decoding = "async";
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`이미지 로드 실패: ${src}`));
    img.src = src;
  });
}

async function init() {
  setStatus("템플릿을 준비 중입니다...");
  applyDefaults();
  bindInputs();
  refs.downloadBtn.addEventListener("click", downloadTemplate);
  refs.resetBtn.addEventListener("click", () => {
    applyDefaults();
    updateTemplate();
  });

  try {
    const [bg, logo] = await Promise.all([
      loadImage("./assets/Jungrang-cheon.png"),
      loadImage("./assets/logo.png"),
    ]);
    images.bg = bg;
    images.logo = logo;
    setStatus("");
    updateTemplate();
  } catch (err) {
    setStatus(err?.message || "이미지를 불러오지 못했습니다.");
  }
}

document.addEventListener("DOMContentLoaded", init);
