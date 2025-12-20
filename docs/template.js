const CANVAS_SIZE = { width: 1080, height: 1350 };
const BOARD_CANVAS_SIZE = { width: 1080, height: 1080 };
const BOARDS_URL = "./data/boards.json";

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
  note: "오늘의 한 줄을 적어주세요.",
  placeholder: true,
};

const refs = {
  name: document.getElementById("tplName"),
  tier: document.getElementById("tplTier"),
  date: document.getElementById("tplDate"),
  summary: document.getElementById("tplSummary"),
  note: document.getElementById("tplNote"),
  placeholder: document.getElementById("tplPlaceholder"),
  downloadBtn: document.getElementById("downloadBtn"),
  resetBtn: document.getElementById("resetBtn"),
  status: document.getElementById("templateStatus"),
  canvas: document.getElementById("templateCanvas"),
  boardCanvas: document.getElementById("boardCanvas"),
  boardStatus: document.getElementById("boardStatus"),
  boardRefreshBtn: document.getElementById("boardRefreshBtn"),
  boardDownloadBtn: document.getElementById("boardDownloadBtn"),
};

const ctx = refs.canvas.getContext("2d");
const boardCtx = refs.boardCanvas.getContext("2d");
const images = {
  bg: null,
  logo: null,
};
let boards = [];

function setStatus(message) {
  refs.status.textContent = message || "";
}

function setBoardStatus(message) {
  refs.boardStatus.textContent = message || "";
}

function formatDate(value) {
  const dateValue = value || new Date().toISOString().slice(0, 10);
  return dateValue.replace(/-/g, ".");
}

function getValue(input, fallback) {
  return (input.value || "").trim() || fallback;
}

function drawCover(context, img, x, y, w, h) {
  const scale = Math.max(w / img.width, h / img.height);
  const iw = img.width * scale;
  const ih = img.height * scale;
  const ix = x + (w - iw) / 2;
  const iy = y + (h - ih) / 2;
  context.drawImage(img, ix, iy, iw, ih);
}

function drawBoardPlaceholder() {
  const width = BOARD_CANVAS_SIZE.width;
  const height = BOARD_CANVAS_SIZE.height;
  refs.boardCanvas.width = width;
  refs.boardCanvas.height = height;
  boardCtx.clearRect(0, 0, width, height);
  boardCtx.fillStyle = "rgba(15, 23, 42, 0.6)";
  boardCtx.fillRect(0, 0, width, height);
  boardCtx.strokeStyle = "rgba(255, 255, 255, 0.18)";
  boardCtx.lineWidth = 2;
  boardCtx.strokeRect(40, 40, width - 80, height - 80);
  boardCtx.fillStyle = "rgba(255, 255, 255, 0.7)";
  boardCtx.font = '600 28px "Segoe UI", system-ui, sans-serif';
  boardCtx.textAlign = "center";
  boardCtx.textBaseline = "middle";
  boardCtx.fillText("빙고판을 불러오지 못했습니다", width / 2, height / 2 - 16);
  boardCtx.font = '500 20px "Segoe UI", system-ui, sans-serif';
  boardCtx.fillText("이름을 확인해 주세요", width / 2, height / 2 + 18);
  boardCtx.textAlign = "left";
  boardCtx.textBaseline = "alphabetic";
}

function roundRect(context, x, y, w, h, r) {
  const radius = Math.min(r, w / 2, h / 2);
  context.beginPath();
  context.moveTo(x + radius, y);
  context.arcTo(x + w, y, x + w, y + h, radius);
  context.arcTo(x + w, y + h, x, y + h, radius);
  context.arcTo(x, y + h, x, y, radius);
  context.arcTo(x, y, x + w, y, radius);
  context.closePath();
}

function truncateText(context, text, maxWidth) {
  if (context.measureText(text).width <= maxWidth) return text;
  let trimmed = text;
  while (trimmed.length > 0 && context.measureText(trimmed + "…").width > maxWidth) {
    trimmed = trimmed.slice(0, -1);
  }
  return trimmed ? trimmed + "…" : "";
}

function wrapText(context, text, maxWidth) {
  const chars = Array.from(text);
  const lines = [];
  let line = "";
  chars.forEach((char) => {
    const testLine = line + char;
    if (context.measureText(testLine).width > maxWidth && line) {
      lines.push(line);
      line = char;
    } else {
      line = testLine;
    }
  });
  if (line) lines.push(line);
  return lines;
}

function drawTextBlock(context, text, x, y, maxWidth, lineHeight, maxLines = 1) {
  if (!text) return;
  if (maxLines <= 1) {
    context.fillText(truncateText(context, text, maxWidth), x, y);
    return;
  }
  const lines = wrapText(context, text, maxWidth);
  const finalLines = lines.slice(0, maxLines);
  finalLines.forEach((line, index) => {
    const isLast = index === maxLines - 1 && lines.length > maxLines;
    const content = isLast ? truncateText(context, line, maxWidth) : line;
    context.fillText(content, x, y + lineHeight * index);
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
  drawTextBlock(ctx, value, x, y + labelSize + 10, width, lineHeight, maxLines);
}

function drawPlaceholderArea(x, y, w, h) {
  ctx.save();
  ctx.strokeStyle = "rgba(255, 255, 255, 0.45)";
  ctx.lineWidth = 3;
  ctx.setLineDash([18, 10]);
  roundRect(ctx, x, y, w, h, 22);
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

  drawCover(ctx, images.bg, 0, 0, width, height);

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
    roundRect(ctx, shotX, shotY, shotW, shotH, 22);
    ctx.stroke();
    ctx.restore();
  }

  const infoX = 90;
  const infoY = shotY + shotH + 36;
  const infoW = shotW;
  const infoH = height - infoY - 80;

  ctx.save();
  roundRect(ctx, infoX, infoY, infoW, infoH, 28);
  ctx.fillStyle = palette.card;
  ctx.fill();
  ctx.restore();

  ctx.save();
  roundRect(ctx, infoX, infoY, infoW, infoH, 28);
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
  const note = getValue(refs.note, defaults.note);

  drawField("이름", name, leftX, rowY1, columnWidth);
  drawField("티어", tierValue, rightX, rowY1, columnWidth);

  drawField("날짜", dateValue, leftX, rowY1 + rowGap, columnWidth, { valueSize: 28 });
  drawField("러닝 요약", summary, rightX, rowY1 + rowGap, columnWidth, { valueSize: 28 });

  drawField("한 줄 기록", note, leftX, rowY1 + rowGap * 2, infoW - padding * 2, {
    valueSize: 24,
    lineHeight: 30,
    maxLines: 2,
  });

  ctx.textAlign = "right";
  ctx.font = '600 18px "Segoe UI", system-ui, sans-serif';
  ctx.fillStyle = "rgba(255, 255, 255, 0.7)";
  ctx.fillText("instagram@modu_running", width - 90, height - 56);
  ctx.fillStyle = "rgba(255, 255, 255, 0.55)";
  ctx.fillText("#모두의러닝겨울방학빙고게임", width - 90, height - 30);
  ctx.textAlign = "left";
}

function normalizeValue(value) {
  return (value || "").trim().toLowerCase();
}

function findBoardMatch() {
  if (!boards || boards.length === 0) return null;
  const nameInput = normalizeValue(refs.name.value);

  let matches = [];
  if (nameInput) {
    matches = boards.filter((board) => normalizeValue(board.name) === nameInput);
  }

  if (matches.length === 0) return null;
  matches.sort((a, b) => {
    const aTime = new Date(a.timestamp || 0).getTime();
    const bTime = new Date(b.timestamp || 0).getTime();
    return bTime - aTime;
  });
  return matches[0];
}

function getTypeColor(type) {
  switch (type) {
    case "A":
      return { fill: "rgba(96, 165, 250, 0.18)", stroke: "rgba(125, 211, 252, 0.9)" };
    case "B":
      return { fill: "rgba(52, 211, 153, 0.18)", stroke: "rgba(52, 211, 153, 0.9)" };
    case "C":
      return { fill: "rgba(251, 191, 36, 0.22)", stroke: "rgba(251, 191, 36, 0.9)" };
    case "D":
      return { fill: "rgba(248, 113, 113, 0.2)", stroke: "rgba(248, 113, 113, 0.9)" };
    case "W":
      return { fill: "rgba(196, 181, 253, 0.22)", stroke: "rgba(196, 181, 253, 0.95)" };
    default:
      return { fill: "rgba(255, 255, 255, 0.08)", stroke: "rgba(255, 255, 255, 0.2)" };
  }
}

function drawBoardGrid(board) {
  const width = BOARD_CANVAS_SIZE.width;
  const height = BOARD_CANVAS_SIZE.height;
  refs.boardCanvas.width = width;
  refs.boardCanvas.height = height;
  boardCtx.clearRect(0, 0, width, height);

  if (images.bg) {
    drawCover(boardCtx, images.bg, 0, 0, width, height);
  } else {
    boardCtx.fillStyle = "#0b1020";
    boardCtx.fillRect(0, 0, width, height);
  }

  const overlay = boardCtx.createLinearGradient(0, 0, 0, height);
  overlay.addColorStop(0, "rgba(11, 16, 32, 0.2)");
  overlay.addColorStop(0.6, "rgba(11, 16, 32, 0.65)");
  overlay.addColorStop(1, "rgba(11, 16, 32, 0.82)");
  boardCtx.fillStyle = overlay;
  boardCtx.fillRect(0, 0, width, height);

  const padding = 32;
  const headerHeight = 120;
  const gridSize = Math.min(width - padding * 2, height - padding * 2 - headerHeight);
  const gridX = (width - gridSize) / 2;
  const gridY = padding + headerHeight;
  const cellSize = gridSize / 5;

  boardCtx.fillStyle = "rgba(15, 23, 42, 0.7)";
  roundRect(boardCtx, gridX - 12, gridY - 12, gridSize + 24, gridSize + 24, 18);
  boardCtx.fill();

  const name = board?.name || getValue(refs.name, defaults.name);
  boardCtx.fillStyle = palette.text;
  boardCtx.font = '700 34px "Segoe UI", system-ui, sans-serif';
  boardCtx.textAlign = "left";
  boardCtx.fillText(name, padding, padding + 34);
  boardCtx.font = '600 20px "Segoe UI", system-ui, sans-serif';
  boardCtx.fillStyle = palette.muted;
  boardCtx.fillText("#모두의러닝겨울방학빙고게임 @modu_running", padding, padding + 66);

  if (images.logo) {
    const logoWidth = 140;
    const logoHeight = (logoWidth / images.logo.width) * images.logo.height;
    const logoX = width - padding - logoWidth;
    const logoY = padding - 6;
    boardCtx.drawImage(images.logo, logoX, logoY, logoWidth, logoHeight);
  }

  boardCtx.textAlign = "left";

  const grid = board?.grid || [];
  for (let row = 0; row < 5; row += 1) {
    for (let col = 0; col < 5; col += 1) {
      const cell = grid[row]?.[col];
      const type = cell?.type || "?";
      const { fill, stroke } = getTypeColor(type);
      const x = gridX + col * cellSize;
      const y = gridY + row * cellSize;

      boardCtx.fillStyle = fill;
      roundRect(boardCtx, x + 4, y + 4, cellSize - 8, cellSize - 8, 14);
      boardCtx.fill();

      boardCtx.strokeStyle = stroke;
      boardCtx.lineWidth = 2;
      roundRect(boardCtx, x + 4, y + 4, cellSize - 8, cellSize - 8, 14);
      boardCtx.stroke();

      if (!cell) continue;

      boardCtx.fillStyle = palette.text;
      boardCtx.font = '700 40px "Segoe UI", system-ui, sans-serif';
      boardCtx.fillText(cell.code || "", x + 12, y + 42);

      boardCtx.font = '500 28px "Segoe UI", system-ui, sans-serif';
      const title = cell.title || "";
      const titleLines = wrapText(boardCtx, title, cellSize - 24).slice(0, 2);
      titleLines.forEach((line, index) => {
        boardCtx.fillText(line, x + 12, y + 86 + index * 32);
      });

      if (cell.stars) {
        boardCtx.font = '600 32px "Segoe UI", system-ui, sans-serif';
        const stars = "★".repeat(cell.stars);
        boardCtx.fillStyle = "rgba(255, 255, 255, 0.8)";
        boardCtx.fillText(stars, x + 12, y + cellSize - 10);
      }
    }
  }
}

function renderBoard() {
  if (!refs.boardCanvas) return;
  const board = findBoardMatch();
  if (!board) {
    setBoardStatus("빙고판을 찾지 못했습니다. 이름을 입력해 주세요.");
    drawBoardPlaceholder();
    return;
  }
  setBoardStatus(`빙고판 로드 완료 · ${board.name || "-"} (${board.id?.slice(0, 8) || "board"})`);
  drawBoardGrid(board);
}

function downloadBoard() {
  if (!refs.boardCanvas) return;
  try {
    const dateStamp = formatDate(refs.date.value).replace(/\./g, "");
    const filename = `mrc_binggo_board_${dateStamp}.png`;
    const link = document.createElement("a");
    link.href = refs.boardCanvas.toDataURL("image/png");
    link.download = filename;
    link.click();
    setBoardStatus("빙고판 PNG가 다운로드되었습니다.");
  } catch (err) {
    setBoardStatus("빙고판 PNG 생성에 실패했습니다.");
  }
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
  if (refs.boardRefreshBtn) {
    refs.boardRefreshBtn.addEventListener("click", renderBoard);
  }
  if (refs.boardDownloadBtn) {
    refs.boardDownloadBtn.addEventListener("click", downloadBoard);
  }

  if (refs.name) {
    refs.name.addEventListener("input", renderBoard);
  }

  try {
    const [bg, logo, boardsRes] = await Promise.all([
      loadImage("./assets/Jungrang-cheon.png"),
      loadImage("./assets/logo.png"),
      fetch(BOARDS_URL, { cache: "no-store" }),
    ]);
    images.bg = bg;
    images.logo = logo;
    if (boardsRes.ok) {
      const boardsJson = await boardsRes.json();
      boards = Array.isArray(boardsJson.boards) ? boardsJson.boards : [];
    } else {
      setBoardStatus("빙고판 데이터를 불러오지 못했습니다.");
      drawBoardPlaceholder();
    }
    setStatus("");
    updateTemplate();
    if (boardsRes.ok) renderBoard();
  } catch (err) {
    setStatus(err?.message || "이미지를 불러오지 못했습니다.");
    setBoardStatus("빙고판 데이터를 불러오지 못했습니다.");
    drawBoardPlaceholder();
  }
}

document.addEventListener("DOMContentLoaded", init);
