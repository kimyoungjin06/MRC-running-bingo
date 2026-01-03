const CANVAS_SIZE = { width: 1080, height: 1350 };
const BOARD_CANVAS_SIZE = { width: 1080, height: 1080 };
const DEFAULT_BOARDS_URL = "./data/boards.json";
const DEFAULT_PROGRESS_URL = "./data/progress.json";
const DEFAULT_API_BASE = "https://payday-congressional-till-exposure.trycloudflare.com";

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

const badgeStyles = {
  bingo: {
    fill: "rgba(59, 130, 246, 0.28)",
    stroke: "rgba(96, 165, 250, 0.9)",
    text: "rgba(219, 234, 254, 0.98)",
  },
  full: {
    fill: "rgba(251, 191, 36, 0.3)",
    stroke: "rgba(251, 191, 36, 0.9)",
    text: "rgba(254, 243, 199, 0.98)",
  },
  first: {
    fill: "rgba(245, 158, 11, 0.32)",
    stroke: "rgba(245, 158, 11, 0.95)",
    text: "rgba(255, 247, 237, 0.98)",
  },
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
  boardShowChecks: document.getElementById("boardShowChecks"),
  boardShowEffects: document.getElementById("boardShowEffects"),
};

const ctx = refs.canvas.getContext("2d");
const boardCtx = refs.boardCanvas.getContext("2d");
const images = {
  bg: null,
  logo: null,
};
let boards = [];
let progressLookup = { byId: new Map(), byName: new Map() };
let boardFallbackNotice = "";

function normalizeBaseUrl(url) {
  return (url || "").trim().replace(/\/+$/, "");
}

function getApiBase() {
  const stored = localStorage.getItem("mrc_submit_api_base");
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
  ctx.fillText("MRC Bingo 2025W · Personal Proof Template", width / 2, logoY + logoHeight + 80);

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

function getProgressForBoard(board) {
  if (!board) return null;
  if (board.player_id && progressLookup.byId.has(board.player_id)) {
    return progressLookup.byId.get(board.player_id);
  }
  if (board.name && progressLookup.byName.has(board.name)) {
    return progressLookup.byName.get(board.name);
  }
  return null;
}

function getCheckedCodes(progress) {
  if (!progress || !Array.isArray(progress.checked_codes)) return new Set();
  return new Set(progress.checked_codes);
}

function shouldShowChecks() {
  if (!refs.boardShowChecks) return true;
  return refs.boardShowChecks.checked;
}

function shouldShowEffects() {
  if (!refs.boardShowEffects) return true;
  return refs.boardShowEffects.checked;
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

function buildBoardLines(grid) {
  const lines = [];
  if (!Array.isArray(grid) || grid.length !== 5 || grid.some((row) => !Array.isArray(row) || row.length !== 5)) {
    return lines;
  }

  for (let row = 0; row < 5; row += 1) {
    const line = [];
    for (let col = 0; col < 5; col += 1) {
      const code = grid[row][col]?.code;
      if (!code) {
        line.length = 0;
        break;
      }
      line.push({ row, col, code });
    }
    if (line.length === 5) lines.push(line);
  }

  for (let col = 0; col < 5; col += 1) {
    const line = [];
    for (let row = 0; row < 5; row += 1) {
      const code = grid[row][col]?.code;
      if (!code) {
        line.length = 0;
        break;
      }
      line.push({ row, col, code });
    }
    if (line.length === 5) lines.push(line);
  }

  const diag1 = [];
  const diag2 = [];
  for (let i = 0; i < 5; i += 1) {
    const code1 = grid[i][i]?.code;
    const code2 = grid[i][4 - i]?.code;
    if (!code1 || !code2) {
      diag1.length = 0;
      diag2.length = 0;
      break;
    }
    diag1.push({ row: i, col: i, code: code1 });
    diag2.push({ row: i, col: 4 - i, code: code2 });
  }
  if (diag1.length === 5) lines.push(diag1);
  if (diag2.length === 5) lines.push(diag2);

  return lines;
}

function getCompletedLines(lines, checkedCodes) {
  if (!lines.length || checkedCodes.size === 0) return [];
  return lines.filter((line) => line.every((cell) => checkedCodes.has(cell.code)));
}

function drawCheckedOverlay(x, y, size) {
  boardCtx.save();
  boardCtx.fillStyle = "rgba(34, 197, 94, 0.18)";
  roundRect(boardCtx, x + 6, y + 6, size - 12, size - 12, 12);
  boardCtx.fill();
  boardCtx.restore();
}

function drawCheckMark(x, y, size) {
  boardCtx.save();
  const cx = x + size - 26;
  const cy = y + 26;
  boardCtx.beginPath();
  boardCtx.fillStyle = "rgba(34, 197, 94, 0.9)";
  boardCtx.arc(cx, cy, 16, 0, Math.PI * 2);
  boardCtx.fill();
  boardCtx.fillStyle = "#0b1020";
  boardCtx.font = '700 18px "Segoe UI", system-ui, sans-serif';
  boardCtx.textAlign = "center";
  boardCtx.textBaseline = "middle";
  boardCtx.fillText("✓", cx, cy + 1);
  boardCtx.restore();
}

function drawBingoLines(lines, gridX, gridY, cellSize, color) {
  if (!lines.length) return;
  boardCtx.save();
  boardCtx.strokeStyle = color || "rgba(251, 191, 36, 0.75)";
  boardCtx.lineWidth = 10;
  boardCtx.lineCap = "round";
  boardCtx.shadowColor = color || "rgba(251, 191, 36, 0.6)";
  boardCtx.shadowBlur = 18;
  lines.forEach((line) => {
    const first = line[0];
    const last = line[line.length - 1];
    const x1 = gridX + (first.col + 0.5) * cellSize;
    const y1 = gridY + (first.row + 0.5) * cellSize;
    const x2 = gridX + (last.col + 0.5) * cellSize;
    const y2 = gridY + (last.row + 0.5) * cellSize;
    boardCtx.beginPath();
    boardCtx.moveTo(x1, y1);
    boardCtx.lineTo(x2, y2);
    boardCtx.stroke();
  });
  boardCtx.restore();
}

function drawAchievementBadges(badges, x, y, maxWidth, height = 28, fontSize = 18) {
  if (!badges.length) return;
  boardCtx.save();
  boardCtx.textAlign = "left";
  boardCtx.textBaseline = "middle";
  boardCtx.font = `700 ${fontSize}px "Segoe UI", system-ui, sans-serif`;
  let offsetX = x;
  const limit = maxWidth ? x + maxWidth : null;
  badges.forEach((badge) => {
    const style = badgeStyles[badge.style] || badgeStyles.bingo;
    const textWidth = boardCtx.measureText(badge.text).width;
    const padX = 14;
    const width = textWidth + padX * 2;
    if (limit && offsetX + width > limit) {
      return;
    }
    roundRect(boardCtx, offsetX, y, width, height, 16);
    boardCtx.fillStyle = style.fill;
    boardCtx.fill();
    boardCtx.strokeStyle = style.stroke;
    boardCtx.lineWidth = 2;
    boardCtx.stroke();
    boardCtx.fillStyle = style.text;
    boardCtx.fillText(badge.text, offsetX + padX, y + height / 2 + 1);
    offsetX += width + 8;
  });
  boardCtx.restore();
}

function drawBoardGrid(board, progress) {
  const width = BOARD_CANVAS_SIZE.width;
  const height = BOARD_CANVAS_SIZE.height;
  refs.boardCanvas.width = width;
  refs.boardCanvas.height = height;
  boardCtx.clearRect(0, 0, width, height);

  const showChecks = shouldShowChecks();
  const showEffects = shouldShowEffects();
  const checkedCodes = getCheckedCodes(progress);

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
  const nameFont = '700 34px "Segoe UI", system-ui, sans-serif';
  const nameBaseline = padding + 34;
  boardCtx.fillStyle = palette.text;
  boardCtx.font = nameFont;
  boardCtx.textAlign = "left";
  boardCtx.fillText(name, padding, nameBaseline);
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

  const grid = Array.isArray(board?.grid) ? board.grid : [];
  const boardLines = showEffects ? buildBoardLines(grid) : [];
  const completedLines = showEffects ? getCompletedLines(boardLines, checkedCodes) : [];
  const checkedCount = typeof progress?.checked === "number" ? progress.checked : checkedCodes.size;
  const bingoCount = typeof progress?.bingo === "number" ? progress.bingo : completedLines.length;
  const achievements = progress?.achievements || {};
  const hasFull = achievements.full || checkedCount >= 25 || checkedCodes.size >= 25;
  const hasBingo5 = achievements.bingo5 || bingoCount >= 5 || completedLines.length >= 5;
  const glowColor = showEffects
    ? achievements.first_full
      ? "rgba(245, 158, 11, 0.95)"
      : hasFull
        ? "rgba(251, 191, 36, 0.85)"
        : hasBingo5
          ? "rgba(59, 130, 246, 0.7)"
          : null
    : null;

  const badges = [];
  if (showEffects) {
    if (achievements.first_full) badges.push({ text: "퍼스트 올빙고", style: "first" });
    else if (hasFull) badges.push({ text: "올빙고", style: "full" });
    if (achievements.first_bingo5) badges.push({ text: "퍼스트 5빙고", style: "first" });
    else if (hasBingo5) badges.push({ text: "5빙고", style: "bingo" });
  }

  if (badges.length > 0) {
    boardCtx.font = nameFont;
    const nameWidth = boardCtx.measureText(name).width;
    const badgesX = padding + nameWidth + 16;
    const maxWidth = width - badgesX - padding - 8;
    const badgeHeight = 24;
    const badgeY = nameBaseline - badgeHeight + 4;
    drawAchievementBadges(badges, badgesX, badgeY, maxWidth, badgeHeight, 16);
  }

  if (glowColor) {
    boardCtx.save();
    boardCtx.strokeStyle = glowColor;
    boardCtx.lineWidth = 6;
    boardCtx.shadowColor = glowColor;
    boardCtx.shadowBlur = 24;
    roundRect(boardCtx, gridX - 14, gridY - 14, gridSize + 28, gridSize + 28, 20);
    boardCtx.stroke();
    boardCtx.restore();
  }

  const cellMeta = [];
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

      cellMeta.push({ cell, x, y, size: cellSize });
    }
  }

  if (showChecks && checkedCodes.size > 0) {
    cellMeta.forEach(({ cell, x, y, size }) => {
      if (!cell?.code || !checkedCodes.has(cell.code)) return;
      drawCheckedOverlay(x, y, size);
    });
  }

  if (showEffects && completedLines.length > 0) {
    const lineColor = glowColor || "rgba(251, 191, 36, 0.75)";
    drawBingoLines(completedLines, gridX, gridY, cellSize, lineColor);
  }

  cellMeta.forEach(({ cell, x, y, size }) => {
    if (!cell) return;

    boardCtx.fillStyle = palette.text;
    boardCtx.font = '700 40px "Segoe UI", system-ui, sans-serif';
    boardCtx.fillText(cell.code || "", x + 12, y + 38);

    boardCtx.font = '500 28px "Segoe UI", system-ui, sans-serif';
    const title = cell.title || "";
    const titleLines = wrapText(boardCtx, title, size - 24).slice(0, 2);
    titleLines.forEach((line, index) => {
      boardCtx.fillText(line, x + 12, y + 78 + index * 28);
    });

    if (cell.stars) {
      boardCtx.font = '600 32px "Segoe UI", system-ui, sans-serif';
      const stars = "★".repeat(cell.stars);
      boardCtx.fillStyle = "rgba(255, 255, 255, 0.8)";
      boardCtx.fillText(stars, x + 12, y + size - 14);
    }
  });

  if (showChecks && checkedCodes.size > 0) {
    cellMeta.forEach(({ cell, x, y, size }) => {
      if (!cell?.code || !checkedCodes.has(cell.code)) return;
      drawCheckMark(x, y, size);
    });
  }
}

async function loadBoardsAndProgress() {
  const boardsUrl = getBoardsUrl();
  const progressUrl = getProgressUrl();
  const fallbackBoards = boardsUrl !== DEFAULT_BOARDS_URL ? DEFAULT_BOARDS_URL : boardsUrl;
  const fallbackProgress = progressUrl !== DEFAULT_PROGRESS_URL ? DEFAULT_PROGRESS_URL : progressUrl;

  const boardsResult = await loadJsonWithFallback(boardsUrl, fallbackBoards);
  boards = Array.isArray(boardsResult.data?.boards) ? boardsResult.data.boards : [];

  let progressResult = { data: { players: [] }, fallback: false };
  try {
    progressResult = await loadJsonWithFallback(progressUrl, fallbackProgress);
  } catch {
    progressResult = { data: { players: [] }, fallback: true };
  }

  progressLookup = { byId: new Map(), byName: new Map() };
  const players = Array.isArray(progressResult.data?.players) ? progressResult.data.players : [];
  players.forEach((player) => {
    if (player.id) progressLookup.byId.set(player.id, player);
    if (player.name) progressLookup.byName.set(player.name, player);
  });

  boardFallbackNotice = boardsResult.fallback || progressResult.fallback ? "서버 접속 불가: 예시 데이터" : "";
}

async function refreshBoardData() {
  if (!refs.boardCanvas) return;
  setBoardStatus("빙고판 불러오는 중...");
  try {
    await loadBoardsAndProgress();
    renderBoard();
  } catch (err) {
    setBoardStatus(err?.message || "빙고판 데이터를 불러오지 못했습니다.");
    drawBoardPlaceholder();
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
  const progress = getProgressForBoard(board);
  const checkedCodes = getCheckedCodes(progress);
  const checkedCount = typeof progress?.checked === "number" ? progress.checked : checkedCodes.size;
  const statusParts = [
    `빙고판 로드 완료`,
    board.name || "-",
    `(${board.id?.slice(0, 8) || "board"})`,
  ];
  if (progress) {
    statusParts.push(`진행도 ${checkedCount}/25`);
  } else {
    statusParts.push("진행도 없음");
  }
  if (boardFallbackNotice) statusParts.push(boardFallbackNotice);
  setBoardStatus(statusParts.join(" · "));
  drawBoardGrid(board, progress);
}

function downloadBoard() {
  if (!refs.boardCanvas) return;
  try {
    const dateStamp = formatDate(refs.date.value).replace(/\./g, "");
    const filename = `mrc_bingo_board_${dateStamp}.png`;
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
    const filename = `mrc_bingo_template_${dateStamp}.png`;
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

function bindBoardOptions() {
  if (refs.boardShowChecks) {
    refs.boardShowChecks.addEventListener("change", renderBoard);
  }
  if (refs.boardShowEffects) {
    refs.boardShowEffects.addEventListener("change", renderBoard);
  }
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
    refs.boardRefreshBtn.addEventListener("click", refreshBoardData);
  }
  if (refs.boardDownloadBtn) {
    refs.boardDownloadBtn.addEventListener("click", downloadBoard);
  }

  if (refs.name) {
    refs.name.addEventListener("input", renderBoard);
  }
  bindBoardOptions();

  try {
    const [bg, logo] = await Promise.all([
      loadImage("./assets/Jungrang-cheon.png"),
      loadImage("./assets/logo.png"),
    ]);
    images.bg = bg;
    images.logo = logo;
    setStatus("");
    updateTemplate();
    await refreshBoardData();
  } catch (err) {
    setStatus(err?.message || "이미지를 불러오지 못했습니다.");
    setBoardStatus("빙고판 데이터를 불러오지 못했습니다.");
    drawBoardPlaceholder();
  }
}

document.addEventListener("DOMContentLoaded", init);
