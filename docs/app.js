const PAGES = {
  intro: {
    title: "소개",
    file: "intro.md",
    meta: "게임 개요와 빠른 시작",
    githubPath: "README.md",
  },
  rulebook: {
    title: "룰북",
    file: "rulebook.md",
    meta: "게임 규칙(세팅/체크 상한/Wild 토큰)",
    githubPath: "RuleBook.md",
  },
  carddeck: {
    title: "카드 덱",
    file: "carddeck.md",
    meta: "40장 카드 목록(운영진용/선택 종료 후 공개 권장)",
    githubPath: "CardDeck.md",
  },
  formanagement: {
    title: "운영진 매뉴얼",
    file: "formanager.md",
    meta: "운영 루틴/검증/예외처리",
    githubPath: "ForManager.md",
  },
};

function escapeHtml(raw) {
  return raw
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderInline(text) {
  const escaped = escapeHtml(text);
  return escaped
    .replace(/!\[([^\]]*?)\]\(([^)]+?)\)/g, '<img src="$2" alt="$1" loading="lazy" />')
    .replace(/\[([^\]]+?)\]\(([^)]+?)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
    .replace(/`([^`]+?)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+?)\*\*/g, "<strong>$1</strong>");
}

function markdownToHtml(md) {
  const lines = md.replaceAll("\r\n", "\n").split("\n");
  const out = [];
  let inCode = false;
  let codeLang = "";
  let listStack = null; // {type: 'ul'|'ol'}
  let blockquote = false;

  function closeList() {
    if (!listStack) return;
    out.push(`</${listStack.type}>`);
    listStack = null;
  }

  function closeBlockquote() {
    if (!blockquote) return;
    out.push("</blockquote>");
    blockquote = false;
  }

  let paragraph = [];
  function flushParagraph() {
    if (paragraph.length === 0) return;
    const html = paragraph
      .map((l) => {
        if (/\s\s$/.test(l)) return `${renderInline(l.trimEnd())}<br />`;
        return renderInline(l);
      })
      .join(" ");
    out.push(`<p>${html}</p>`);
    paragraph = [];
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (inCode) {
      if (line.startsWith("```")) {
        out.push("</code></pre>");
        inCode = false;
        codeLang = "";
      } else {
        out.push(escapeHtml(line));
      }
      continue;
    }

    if (line.startsWith("```")) {
      flushParagraph();
      closeList();
      closeBlockquote();
      inCode = true;
      codeLang = line.slice(3).trim();
      const langAttr = codeLang ? ` class="language-${escapeHtml(codeLang)}"` : "";
      out.push(`<pre><code${langAttr}>`);
      continue;
    }

    if (/^\s*$/.test(line)) {
      flushParagraph();
      closeList();
      closeBlockquote();
      continue;
    }

    const hr = /^---+$/.test(line.trim());
    if (hr) {
      flushParagraph();
      closeList();
      closeBlockquote();
      out.push("<hr />");
      continue;
    }

    const heading = /^(#{1,6})\s+(.+)$/.exec(line);
    if (heading) {
      flushParagraph();
      closeList();
      closeBlockquote();
      const level = heading[1].length;
      out.push(`<h${level}>${renderInline(heading[2].trim())}</h${level}>`);
      continue;
    }

    const bq = /^>\s?(.*)$/.exec(line);
    if (bq) {
      flushParagraph();
      closeList();
      if (!blockquote) {
        out.push("<blockquote>");
        blockquote = true;
      }
      out.push(`<p>${renderInline(bq[1])}</p>`);
      continue;
    }

    const ul = /^-\s+(.+)$/.exec(line);
    const ol = /^(\d+)[.)]\s+(.+)$/.exec(line);
    if (ul || ol) {
      flushParagraph();
      closeBlockquote();
      const type = ul ? "ul" : "ol";
      const itemText = ul ? ul[1] : ol[2];
      if (!listStack || listStack.type !== type) {
        closeList();
        out.push(`<${type}>`);
        listStack = { type };
      }
      out.push(`<li>${renderInline(itemText.trim())}</li>`);
      continue;
    }

    paragraph.push(line.trim());
  }

  flushParagraph();
  closeList();
  closeBlockquote();

  return out.join("\n");
}

function getGitHubRepoInfo() {
  const host = window.location.hostname;
  const parts = window.location.pathname.split("/").filter(Boolean);
  if (!host.endsWith("github.io") || parts.length < 1) return null;
  const user = host.split(".")[0];
  const repo = parts[0];
  return { user, repo };
}

function getPageKeyFromHash() {
  const raw = (window.location.hash || "#intro").slice(1).trim().toLowerCase();
  if (!raw) return "intro";
  if (raw === "formanager" || raw === "for-manager" || raw === "manager" || raw === "for")
    return "formanager";
  if (PAGES[raw]) return raw;
  return "intro";
}

function setActiveNav(pageKey) {
  document.querySelectorAll(".nav__link").forEach((a) => {
    if (a.dataset.page === pageKey) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
}

async function loadPage(pageKey) {
  const normalizedKey = pageKey === "formanager" ? "formanagement" : pageKey;
  const info = PAGES[normalizedKey] ?? PAGES.intro;
  const titleEl = document.getElementById("docTitle");
  const metaEl = document.getElementById("docMeta");
  const bodyEl = document.getElementById("docBody");
  const githubLink = document.getElementById("githubLink");

  setActiveNav(pageKey);
  titleEl.textContent = info.title;
  metaEl.textContent = info.meta;
  bodyEl.innerHTML = `<p>불러오는 중…</p>`;

  const gh = getGitHubRepoInfo();
  githubLink.href = gh
    ? `https://github.com/${gh.user}/${gh.repo}/blob/main/${info.githubPath}`
    : `./`;

  try {
    const res = await fetch(`./content/${info.file}`, { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const md = await res.text();
    bodyEl.innerHTML = markdownToHtml(md);
  } catch (e) {
    bodyEl.innerHTML =
      `<p>문서를 불러오지 못했습니다. (<code>${escapeHtml(String(e))}</code>)</p>` +
      `<p>경로: <code>docs/content/${escapeHtml(info.file)}</code></p>`;
  }
}

function applyTheme(theme) {
  const root = document.documentElement;
  if (theme === "light" || theme === "dark") root.dataset.theme = theme;
  else delete root.dataset.theme;
}

function getPreferredTheme() {
  return localStorage.getItem("theme") || "system";
}

function toggleTheme() {
  const current = getPreferredTheme();
  const next = current === "system" ? "dark" : current === "dark" ? "light" : "system";
  localStorage.setItem("theme", next);
  applyTheme(next === "system" ? "" : next);
  updateThemeButton();
}

function updateThemeButton() {
  const btn = document.getElementById("themeToggle");
  const mode = getPreferredTheme();
  btn.textContent = mode === "system" ? "테마: 시스템" : mode === "dark" ? "테마: 다크" : "테마: 라이트";
}

function wireSearch() {
  const input = document.getElementById("searchInput");
  const bodyEl = document.getElementById("docBody");
  let last = "";

  function clearHighlights() {
    bodyEl.querySelectorAll("mark[data-hit='1']").forEach((m) => {
      const parent = m.parentNode;
      parent.replaceChild(document.createTextNode(m.textContent || ""), m);
      parent.normalize();
    });
  }

  function highlight(term) {
    if (!term) return;
    const walker = document.createTreeWalker(bodyEl, NodeFilter.SHOW_TEXT);
    const targets = [];
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (!node.nodeValue) continue;
      if (node.parentElement && ["SCRIPT", "STYLE", "CODE", "PRE"].includes(node.parentElement.tagName))
        continue;
      if (node.nodeValue.toLowerCase().includes(term.toLowerCase())) targets.push(node);
    }

    for (const node of targets) {
      const text = node.nodeValue;
      const idx = text.toLowerCase().indexOf(term.toLowerCase());
      if (idx < 0) continue;
      const before = document.createTextNode(text.slice(0, idx));
      const hit = document.createElement("mark");
      hit.dataset.hit = "1";
      hit.textContent = text.slice(idx, idx + term.length);
      const after = document.createTextNode(text.slice(idx + term.length));
      const parent = node.parentNode;
      parent.replaceChild(after, node);
      parent.insertBefore(hit, after);
      parent.insertBefore(before, hit);
    }
  }

  input.addEventListener("input", () => {
    const term = input.value.trim();
    if (term === last) return;
    clearHighlights();
    if (term.length >= 2) highlight(term);
    last = term;
  });
}

function wireCopyLink() {
  const btn = document.getElementById("copyLink");
  btn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      btn.textContent = "복사됨";
      window.setTimeout(() => (btn.textContent = "링크 복사"), 900);
    } catch {
      btn.textContent = "복사 실패";
      window.setTimeout(() => (btn.textContent = "링크 복사"), 900);
    }
  });
}

window.addEventListener("hashchange", () => loadPage(getPageKeyFromHash()));

window.addEventListener("DOMContentLoaded", () => {
  const theme = getPreferredTheme();
  applyTheme(theme === "system" ? "" : theme);
  updateThemeButton();

  document.getElementById("themeToggle").addEventListener("click", toggleTheme);
  wireSearch();
  wireCopyLink();
  loadPage(getPageKeyFromHash());
});
