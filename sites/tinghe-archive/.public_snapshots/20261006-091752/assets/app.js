/* 听荷轩 · 残荷诡影 — hash-routed reader + archive SPA.
   No build step, no framework. Data loads are memoised by promise so a repeated
   render can never double-fetch, and the 514KB world snapshot is only pulled
   on #/world — the homepage reads data/counts.json instead. */
(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const view = $("#view");

  const escapeHtml = (value = "") =>
    String(value).replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
  const list = value => (Array.isArray(value) ? value : []);
  const fmt = n => Number(n || 0).toLocaleString("zh-CN");
  const pad3 = n => String(n).padStart(3, "0");

  /* ---------- data (memoised in-flight promises) ---------- */

  const inflight = new Map();
  function data(key, path) {
    if (!inflight.has(key)) {
      inflight.set(key, fetch(path).then(async r => {
        // Cloudflare Pages answers unknown paths with the SPA shell and a 200,
        // so a status check alone is not enough: require real JSON back.
        const type = r.headers.get("content-type") || "";
        if (!r.ok || !type.includes("json")) {
          throw new Error(r.ok
            ? `${path} 不存在（服务器返回了页面而不是数据）`
            : `${path} 响应 ${r.status}`);
        }
        return r.json();
      }).catch(err => {
        inflight.delete(key);   // let a later visit retry a transient failure
        throw err;
      }));
    }
    return inflight.get(key);
  }
  const loadBook = () => data("book", "data/book.json");
  const loadCounts = () => data("counts", "data/counts.json");
  const loadSnapshot = () => data("snapshot", "data/snapshot.v1.json");
  const loadDesk = () => data("desk", "data/originals/desk.json");
  const loadState = () => data("state", "data/story-state.v1.json").catch(() => ({}));
  const loadSearchIndex = () => data("search", "data/search-index.json").catch(() => ({ entries: [] }));

  /* ---------- persisted preferences ---------- */

  const KEY = {
    reader: "tinghe.reader.progress",
    font: "tinghe.reader.font",
    theme: "tinghe.theme",
  };
  const readStore = (key, fallback) => {
    try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
  };
  const saveProgress = id => localStorage.setItem(KEY.reader, JSON.stringify({ id, t: Date.now() }));
  const lastRead = () => readStore(KEY.reader, {}).id || "";

  const FONTS = ["s", "m", "l"];
  const applyFont = size => {
    document.documentElement.dataset.font = size;
    localStorage.setItem(KEY.font, size);
  };
  const applyTheme = theme => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(KEY.theme, theme);
    const btn = $("[data-tool=\"theme\"]");
    if (btn) {
      btn.setAttribute("aria-pressed", String(theme === "night"));
      btn.title = theme === "night" ? "回到日间" : "夜间阅读";
    }
  };
  applyFont(FONTS.includes(readStore(KEY.font, "m")) ? readStore(KEY.font, "m") : "m");
  applyTheme(readStore(KEY.theme, "day") === "night" ? "night" : "day");

  /* ---------- chrome ---------- */

  function setActiveNav(route) {
    document.querySelectorAll("[data-nav]").forEach(link => link.removeAttribute("aria-current"));
    const key = { home: "home", catalog: "catalog", read: "read", world: "world", desk: "desk" }[route] || "home";
    const link = $(`[data-nav="${key}"]`);
    if (link) link.setAttribute("aria-current", "page");
  }
  const focusMain = () => view.focus({ preventScroll: true });

  function pageTitle(title) { document.title = `${title} · 听荷轩`; }

  function errorBox(err) {
    view.innerHTML = `<div class="notice"><b>这一页暂时打不开。</b><br>${escapeHtml(err && err.message || err)}</div>`;
  }

  /* ---------- shared fragments ---------- */

  const sectionHead = (id, eyebrow, title, side = "") => `
    <div class="section-head">
      <div><p class="eyebrow">${escapeHtml(eyebrow)}</p><h2 id="${id}">${escapeHtml(title)}</h2></div>
      ${side ? `<div class="head-side">${side}</div>` : ""}
    </div>`;

  const metric = (label, value, tone = "") =>
    `<span class="metric ${tone}"><b>${escapeHtml(value)}</b><small>${escapeHtml(label)}</small></span>`;

  /* `book.json` ships an empty `chars` array for every scene, so pull the cast
   out of the preview's 在场：line instead of rendering nothing. */
  function castOf(ch) {
    if (list(ch.chars).length) return list(ch.chars);
    const hit = /在场[：:]\s*([\s\S]{2,160})/.exec(ch.preview || "");
    if (!hit) return [];

    // The cast list ends at the first top-level "：" (the next speaker's turn).
    let run = "", depth = 0;
    for (const c of hit[1]) {
      if (c === "（") depth++;
      else if (c === "）") depth--;
      else if (c === "：" && depth === 0) break;
      run += c;
    }

    const parts = [];
    let cur = "";
    depth = 0;
    for (const c of run) {
      if (c === "（") depth++;
      else if (c === "）") depth--;
      if (c === "、" && depth === 0) { parts.push(cur); cur = ""; } else cur += c;
    }
    parts.push(cur);

    return parts
      .map(s => s.split("（")[0].split(/\s+/)[0].replace(/[，,。；;、].*$/, "").trim())
      .filter(s => s && s !== "未出场" && s.length <= 12);
  }

  function chapterCard(ch) {
    // The scene title already ends with the place, so only add it when it differs.
    const placeInTitle = ch.place && ch.title.indexOf(ch.place) !== -1;
    const where = placeInTitle ? (ch.time || "") : [ch.time, ch.place].filter(Boolean).join(" · ");
    const cast = castOf(ch);
    const third = cast.length
      ? `人物 ${cast.slice(0, 4).join(" · ")}${cast.length > 4 ? ` +${cast.length - 4}` : ""}`
      : (ch.preview || "").slice(0, 40).trimEnd() + "…";
    return `<li class="chapter-card"><a href="#/read/${escapeHtml(ch.id)}">
      <span class="chapter-no">${escapeHtml(pad3(ch.no))}</span>
      <span class="chapter-body">
        <b>${escapeHtml(ch.title)}</b>
        ${where ? `<small class="truncate">${escapeHtml(where)}</small>` : ""}
        ${third ? `<small class="truncate">${escapeHtml(third)}</small>` : ""}
        <small class="tag">${escapeHtml(ch.wave || "公开快照")}</small>
      </span>
      <span class="chapter-arrow" aria-hidden="true">↗</span>
    </a></li>`;
  }

  /* ---------- home ---------- */

  const ENTRIES = [
    { id: "read", no: "01", glyph: "阅", cls: "entry-read", title: "继续阅读", art: "art-read.svg" },
    { id: "catalog", no: "02", glyph: "卷", cls: "entry-catalog", title: "卷目目录", art: "art-catalog.svg" },
    { id: "characters", no: "03", glyph: "人", cls: "entry-characters", title: "人物簿", art: "art-characters.svg" },
    { id: "places", no: "04", glyph: "地", cls: "entry-places", title: "地点簿", art: "art-places.svg" },
    { id: "events", no: "05", glyph: "事", cls: "entry-events", title: "事件簿", art: "art-events.svg" },
    { id: "props", no: "06", glyph: "物", cls: "entry-props", title: "物件簿", art: "art-props.svg" },
  ];

  function entryCards(resume, counts) {
    const blurb = {
      read: resume.last ? `上次停在第 ${resume.last.no} 场` : "从第一卷荷园夜色起笔",
      catalog: `${fmt(counts.chapter_count)} 场已编目`,
      characters: `${fmt(counts.archive.characters)} 位已现身人物`,
      places: `${fmt(counts.archive.places)} 处被看见的地方`,
      events: `${fmt(counts.archive.events)} 条因果留痕`,
      props: `${fmt(counts.archive.props)} 件仍在场的信物`,
    };
    const href = {
      read: `#/read/${encodeURIComponent(resume.id)}`,
      catalog: "#/catalog",
    };
    return ENTRIES.map(e => `
      <li><a class="entry-card ${e.cls}" ${href[e.id] ? `href="${href[e.id]}"` : 'href="#/world"'} data-entry="${e.id}">
        <span class="entry-art"><span class="entry-no">${e.no}</span><span class="entry-glyph">${e.glyph}</span></span>
        <span class="entry-body">
          <b>${e.title}</b>
          <small>${escapeHtml(blurb[e.id])}</small>
          <span class="entry-more">进入 →</span>
        </span>
      </a></li>`).join("");
  }

  function dashSection(st, counts) {
    const p = st.progress || {}, plot = st.current_plot || {};
    const production = st.production || {};
    const mainline = list(st.mainline).slice(0, 4);
    const chars = list(st.characters).slice(0, 5);
    const fs = st.foreshadowing || {};
    const resolved = list(fs.resolved), open = list(fs.open);
    const latestHref = (production.latest_public && production.latest_public.href) || `#/read/${counts.latest.id}`;

    return `
      <div class="dash">
        <div class="dash-head">
          <div>
            <p class="eyebrow">作品现场 · ${escapeHtml(st.publication_status || "LIVE")}</p>
            <h2>故事自己证明进度</h2>
          </div>
          <span class="status-live"><span class="pulse"></span>静默推进中</span>
        </div>

        <div class="metric-row">
          ${metric("已完成场次", `${fmt(p.completed_scenes || counts.chapter_count)} 场`)}
          ${metric("卷目单元", `${fmt(counts.chapter_count)} 个`)}
          ${metric("已现身人物", `${fmt(counts.archive.characters)} 位`, "is-gold")}
          ${metric("未决物件", `${fmt(counts.archive.props)} 件`, "is-rust")}
        </div>

        <article class="dash-lead">
          <div class="dash-lead-main">
            <p class="dash-kicker">当前剧情 · ${escapeHtml(p.current_label || "推进中")}</p>
            <h3>${escapeHtml(plot.title || p.current_label || "正式剧情持续推进")}</h3>
            <p>${escapeHtml(plot.summary || "正式剧情状态将在下一次发布快照后更新。")}</p>
          </div>
          <dl class="dash-facts">
            <div><dt>当前阶段</dt><dd>${escapeHtml(p.phase || "推进中")}</dd></div>
            <div><dt>下一关注</dt><dd>${escapeHtml(p.next_focus || "待推演")}</dd></div>
          </dl>
          <a class="btn btn-primary btn-sm" href="${escapeHtml(latestHref)}">进入最新内容 <span aria-hidden="true">→</span></a>
        </article>

        <details class="dash-more">
          <summary>展开完整状态<span>主线 ${mainline.length} · 人物 ${chars.length} · 伏笔 ${resolved.length + open.length}</span></summary>
          <div class="dash-grid">
          <article class="dash-card">
            <p class="dash-kicker">主线与冲突</p>
            <ul class="dash-list">
              ${mainline.length ? mainline.map(m => `<li><span class="marker"></span><span><b>${escapeHtml(m.label || "未命名线索")}</b><small>${escapeHtml(m.state || "推进中")} · ${escapeHtml(m.detail || "")}</small></span></li>`).join("")
                : '<li><small>主线尚未公开。</small></li>'}
            </ul>
          </article>
          <article class="dash-card">
            <p class="dash-kicker">人物状态</p>
            <ul class="dash-list">
              ${chars.length ? chars.map(c => `<li><span class="avatar">${escapeHtml((c.name || "人").slice(0, 1))}</span><span><b>${escapeHtml(c.name || "UNKNOWN")}</b><small>${escapeHtml(c.status || "在场")} · ${escapeHtml(c.detail || "")}</small></span></li>`).join("")
                : '<li><small>人物状态尚未公开。</small></li>'}
            </ul>
          </article>
          <article class="dash-card">
            <p class="dash-kicker">伏笔与回收</p>
            <div class="dash-cols">
              <div><b>已回收 ${resolved.length}</b><ul>${resolved.slice(-3).map(x => `<li>${escapeHtml(x)}</li>`).join("") || "<li>暂无</li>"}</ul></div>
              <div><b>仍未决 ${open.length}</b><ul>${open.slice(0, 3).map(x => `<li>${escapeHtml(x)}</li>`).join("") || "<li>暂无</li>"}</ul></div>
            </div>
          </article>
          </div>
        </details>
      </div>`;
  }

  function deskStrip(d) {
    const all = list(d.works);
    if (!all.length) return "";
    // Surface the most recently extended works first: the daily batch appends
    // episodes, so episode count is the only recency signal desk.json carries.
    const works = [...all].sort((a, b) => list(b.episodes).length - list(a.episodes).length);
    const totalEps = all.reduce((n, w) => n + list(w.episodes).length, 0);
    return `
      <section class="section desk-strip" aria-labelledby="desk-strip-title">
        ${sectionHead("desk-strip-title", "独立栏目", "原创桌",
          `<span class="section-note">${fmt(all.length)} 部 · ${fmt(totalEps)} 集</span><a class="quiet-link" href="#/desk">进入栏目 ↗</a>`)}
        <p class="desk-note">这些稿子不进《${escapeHtml(d.canon_work || "残荷诡影")}》正史，只锁身份与空间，不替正文抢戏。每日增量更新。</p>
        <ul class="desk-tiles">${works.map(deskTile).join("")}</ul>
      </section>`;
  }

  async function renderHome() {
    const [book, counts, st, d] = await Promise.all([loadBook(), loadCounts(), loadState(), loadDesk()]);
    const resumeId = lastRead() || counts.latest.id || "c000";
    const resumeChapter = book.chapters.find(c => c.id === resumeId);
    const resume = {
      id: resumeId,
      no: resumeChapter ? resumeChapter.no : "",
      last: resumeChapter,
    };
    const chapters = book.chapters.filter(c => c.id !== "c999");

    view.innerHTML = `
      <section class="hero" aria-labelledby="home-title">
        <div class="hero-copy">
          <p class="eyebrow"><span class="dot"></span>${escapeHtml(book.series)} · 公开阅读快照</p>
          <h1 id="home-title">听荷轩</h1>
          <p class="hero-soul">月下见影，水中藏局；所见未必是真，所失终有其因。</p>
          <p class="hero-lede">${escapeHtml(counts.tagline || book.tagline || "")}</p>
          <div class="hero-actions">
            <a class="btn btn-primary" href="#/read/${encodeURIComponent(resumeId)}">${resume.last ? "继续阅读" : "立即入卷"}<span aria-hidden="true">→</span></a>
            <a class="btn" href="#/catalog">卷目目录 <span aria-hidden="true">⌁</span></a>
            <a class="btn" href="#/world">世界档案</a>
          </div>
          <p class="hero-resume">${resume.last
            ? `上次读到 <b>第 ${escapeHtml(String(resume.no))} 场</b> · ${escapeHtml(resume.last.title)}`
            : `当前公开到 <b>第 ${escapeHtml(String(counts.latest.no))} 场</b> · 共 ${fmt(counts.chapter_count)} 场`}</p>
        </div>
        <figure class="hero-figure">
          <p class="hero-vertical" aria-hidden="true">残荷诡影</p>
          <div class="hero-cover">
            <img src="assets/cover.svg" alt="月下荷园，残荷与水面映出的朦胧人影" width="660" height="880">
            <figcaption>听荷轩藏</figcaption>
          </div>
        </figure>
      </section>

      <section class="section" aria-labelledby="entry-title">
        ${sectionHead("entry-title", "六条入卷路径", "一页一簿，慢慢走进荷园", `<span class="section-note">正式作品 · 持续更新</span>`)}
        <ul class="entry-grid">${entryCards(resume, counts)}</ul>
      </section>

      <section class="section" aria-labelledby="reading-title">
        ${sectionHead("reading-title", "卷中近况", "最近翻动的页",
          `<a class="quiet-link" href="#/catalog">全部 ${fmt(counts.chapter_count)} 场 ↗</a>`)}
        <ul class="chapter-grid">${chapters.slice(-8).reverse().map(chapterCard).join("")}</ul>
      </section>

      <section class="section" aria-labelledby="dash-title">${dashSection(st, counts)}</section>

      <section class="section" aria-label="世界档案概览">
        <div class="status-strip">
          <div class="status-copy">
            <span class="status-live"><span class="pulse"></span>档案仍在生长</span>
            <small>当前公开快照保留 UNKNOWN，不替世界提前下结论。</small>
          </div>
          <div class="metric-row" style="flex:1 1 22rem">
            ${metric("人物", fmt(counts.archive.characters))}
            ${metric("地点", fmt(counts.archive.places))}
            ${metric("事件", fmt(counts.archive.events))}
            ${metric("关系", fmt(counts.archive.relationships), "is-gold")}
            ${metric("未决物件", fmt(counts.archive.props), "is-rust")}
          </div>
        </div>
      </section>

      ${deskStrip(d)}`;

    pageTitle(counts.work || "残荷诡影");
  }

  /* ---------- catalog ---------- */

  function renderCatalog(book) {
    const chapters = book.chapters;
    view.innerHTML = `
      <section class="page-intro">
        <p class="eyebrow">${escapeHtml(book.series)} · 卷目</p>
        <h1>目录</h1>
        <p>按场次进入《${escapeHtml(book.work)}》。每一页都保留它在世界里的时间、地点与人物痕迹。</p>
      </section>
      <div class="catalog-bar">
        <label class="filter-field">
          <span aria-hidden="true">⌕</span>
          <span class="visually-hidden">按标题或地点筛选</span>
          <input id="chapter-filter" type="search" placeholder="按场次、地点或人物筛选" autocomplete="off">
        </label>
        <span class="catalog-count" id="chapter-count" aria-live="polite">${fmt(chapters.length)} 场已编目</span>
        <a class="quiet-link" href="read/">静态目录（可分享）</a>
        <a class="quiet-link" href="#/read/c000">从开篇读起 →</a>
      </div>
      <ol class="catalog" id="chapter-list">${chapters.map(chapterCard).join("")}</ol>`;

    pageTitle("目录");
    const input = $("#chapter-filter");
    const counter = $("#chapter-count");
    input.addEventListener("input", () => {
      const q = input.value.trim().toLowerCase();
      const rows = list(chapters).filter(c => !q || `${c.title} ${c.place} ${c.time} ${c.preview || ""}`.toLowerCase().includes(q));
      $("#chapter-list").innerHTML = rows.length
        ? rows.map(chapterCard).join("")
        : `<li class="empty-state"><b>没有匹配「${escapeHtml(input.value.trim())}」的场次</b>试试只写地点或人物。</li>`;
      counter.textContent = q ? `${fmt(rows.length)} / ${fmt(chapters.length)} 场` : `${fmt(chapters.length)} 场已编目`;
    });
  }

  /* ---------- reader ---------- */

  function readerShell(inner) {
    return `<div class="reader-shell">
      <div class="reader-bar">
        <a class="quiet-link" href="#/catalog">卷目</a>
        <span class="where">${inner.where}</span>
        <div class="reader-tools">
          <button type="button" class="tool" data-tool="font-down" title="缩小字号" aria-label="A− 缩小字号">A−</button>
          <button type="button" class="tool" data-tool="font-up" title="放大字号" aria-label="A+ 放大字号">A+</button>
          <button type="button" class="tool" data-tool="theme" title="夜间阅读" aria-pressed="${document.documentElement.dataset.theme === "night"}">夜</button>
          ${inner.toc === false ? "" : '<button type="button" class="tool" data-tool="toc" title="全部章节" aria-expanded="false">目录</button>'}
        </div>
      </div>
      <div class="reader-progress" aria-hidden="true"><i id="reader-progress-bar"></i></div>
      <article class="reader">${inner.body}</article>
      <nav class="pager" aria-label="章节导航">${inner.pager}</nav>
    </div>
    ${inner.toc === false ? "" : `<div class="toc-backdrop" data-tool="toc-backdrop" hidden></div>
    <aside class="toc" id="toc" hidden aria-label="全部章节">
      <div class="toc-head">
        <h2>卷目</h2>
        <button type="button" class="tool" data-tool="toc-close" aria-label="✕ 关闭目录">✕</button>
      </div>
      <ol class="toc-list" id="toc-list"></ol>
    </aside>`}`;
  }

  /* Reader chrome is wired once and driven by module state, so navigating
     between chapters never stacks duplicate listeners on #view. */
  let readerCtx = null;

  function paintToc() {
    const tocList = $("#toc-list");
    if (!tocList || !readerCtx) return;
    tocList.innerHTML = readerCtx.book.chapters
      .map(c => `<li><a href="#/read/${encodeURIComponent(c.id)}"${c.id === readerCtx.currentId ? ' aria-current="true"' : ""}><span class="n">${escapeHtml(pad3(c.no))}</span><span class="t">${escapeHtml(c.title)}</span></a></li>`)
      .join("");
    $(".toc-list a[aria-current]")?.scrollIntoView({ block: "center" });
  }

  function setToc(show) {
    const toc = $("#toc");
    const backdrop = $("[data-tool='toc-backdrop']");
    if (!toc || !backdrop) return;
    toc.hidden = !show;
    backdrop.hidden = !show;
    $("[data-tool='toc']").setAttribute("aria-expanded", String(show));
    if (show) paintToc();
  }

  function stepFont(delta) {
    const now = document.documentElement.dataset.font || "m";
    applyFont(FONTS[Math.min(FONTS.length - 1, Math.max(0, FONTS.indexOf(now) + delta))]);
  }

  function paintReaderProgress() {
    const bar = $("#reader-progress-bar");
    if (!bar) return;
    const span = document.documentElement.scrollHeight - window.innerHeight;
    bar.style.width = `${span > 0 ? Math.min(100, Math.max(0, (window.scrollY / span) * 100)) : 0}%`;
  }

  /* Lazy images defer ~1MB of covers off the critical path, but some loaders
     (headless Chrome among them) never fire the lazy observer, which would
     leave every cover blank. Give the observer a moment, then promote any
     image that still has not started so a cover is never silently missing. */
  function promoteCovers() {
    const imgs = [...document.querySelectorAll(".desk-cover img")].filter(i => !i.complete);
    if (!imgs.length) return;
    const promote = () => imgs.forEach(img => { if (!img.complete) img.loading = "eager"; });
    if (typeof requestIdleCallback === "function") requestIdleCallback(promote, { timeout: 1500 });
    else setTimeout(promote, 1200);
  }

  function wireChrome() {
    view.addEventListener("click", event => {
      const tool = event.target.closest("[data-tool]");
      if (!tool) return;
      const kind = tool.dataset.tool;
      if (kind === "font-up") stepFont(1);
      else if (kind === "font-down") stepFont(-1);
      else if (kind === "theme") applyTheme(document.documentElement.dataset.theme === "night" ? "day" : "night");
      else if (kind === "toc") setToc(true);
      else if (kind === "toc-close" || kind === "toc-backdrop") setToc(false);
    });
    window.addEventListener("scroll", paintReaderProgress, { passive: true });
    window.addEventListener("resize", paintReaderProgress);
    // One Escape handler for the whole app; both overlays are cheap to close.
    document.addEventListener("keydown", event => {
      if (event.key !== "Escape") return;
      setToc(false);
      wireSearch.dismiss?.();
    });
  }

  async function renderRead(book, id) {
    const idx = Math.max(0, book.chapters.findIndex(c => c.id === id));
    const ch = book.chapters[idx] || book.chapters[0];
    const chapter = await data(`chapter-${ch.id}`, `data/chapters/${encodeURIComponent(ch.id)}.json`);
    saveProgress(ch.id);

    const prev = book.chapters[idx - 1], next = book.chapters[idx + 1];
    const pager = [
      `<a href="${prev ? `#/read/${encodeURIComponent(prev.id)}` : "#/catalog"}"><span aria-hidden="true">←</span> ${prev ? "上一场" : "回到卷目"}</a>`,
      `<a href="#/catalog">目录</a>`,
      `<a href="${next ? `#/read/${encodeURIComponent(next.id)}` : "#/world"}">${next ? "下一场" : "进入世界档案"} <span aria-hidden="true">→</span></a>`,
    ].join("");

    view.innerHTML = readerShell({
      where: `${escapeHtml(book.work)} <b>${escapeHtml(pad3(idx + 1))}</b> / ${book.chapters.length}`,
      body: `<p class="chapter-kicker">${escapeHtml(ch.wave || "卷中")}</p>
        <h1>${escapeHtml(chapter.title || ch.title)}</h1>
        <p class="meta">${escapeHtml([chapter.time || ch.time, chapter.place || ch.place].filter(Boolean).join(" · "))}</p>
        ${chapter.html}`,
      pager,
    });

    // The hash route cannot be shared or indexed, so point readers at the real
    // static document for this scene.
    const tools = $(".reader-tools");
    if (tools) {
      const href = "read/" + encodeURIComponent(ch.id);
      tools.insertAdjacentHTML("beforeend",
        '<a class="tool" href="' + href + '" title="可分享、可被搜索引擎收录的静态页">静态页</a>');
    }

    pageTitle(chapter.title || ch.title);
    readerCtx = { book, currentId: ch.id };
    paintReaderProgress();
    focusMain();
  }

  /* ---------- world archive ---------- */

  const TABS = [
    { id: "characters", label: "人物簿", glyph: "人", head: "谁曾在场" },
    { id: "places", label: "地点簿", glyph: "地", head: "哪里留下回声" },
    { id: "events", label: "事件簿", glyph: "事", head: "什么改变了世界" },
    { id: "props", label: "物件簿", glyph: "物", head: "什么被留下" },
    { id: "relationships", label: "关系簿", glyph: "缘", head: "谁与谁相连" },
  ];
  let archiveTab = "characters";
  let archiveQuery = "";

  const statusDot = tone => `<span class="dot ${tone}"></span>`;

  function archiveEntry(item, i) {
    if (archiveTab === "characters") {
      const scenes = list(item.appearances);
      return `<li class="archive-entry"><span class="entry-index">${String(i + 1).padStart(2, "0")}</span><div>
        <h3>${escapeHtml(item.name)}</h3>
        <p>${statusDot("")}${escapeHtml(item.status || "UNKNOWN")} · 出现 ${escapeHtml(item.source_count || scenes.length || 0)} 场</p>
        <small>${escapeHtml(scenes.slice(0, 5).join(" · ") || "场次 UNKNOWN")}${scenes.length > 5 ? " …" : ""}</small>
      </div></li>`;
    }
    if (archiveTab === "places") {
      return `<li class="archive-entry"><span class="entry-index">${String(i + 1).padStart(2, "0")}</span><div>
        <h3>${escapeHtml(item.name)}</h3><p>${statusDot("is-gold")}${escapeHtml(item.status || "UNKNOWN")} · 被看见 ${escapeHtml(item.seen || 0)} 次</p>
      </div></li>`;
    }
    if (archiveTab === "events") {
      return `<li class="archive-entry is-event"><span class="entry-index">${escapeHtml(item.scene_id || "—")}</span><div>
        <h3>${escapeHtml(item.world_change || "事件内容 UNKNOWN")}</h3>
        <p>${escapeHtml(item.new_information || "新增信息 UNKNOWN")}</p>
        <small>未决：${escapeHtml(item.left_open || "UNKNOWN")}</small>
      </div></li>`;
    }
    if (archiveTab === "props") {
      return `<li class="archive-entry"><span class="entry-index">物</span><div>
        <h3>${escapeHtml(item.name)}</h3>
        <p>${statusDot("is-rust")}${escapeHtml(item.status || "UNKNOWN")} · 见于 ${escapeHtml(item.seen || 0)} 场</p>
      </div></li>`;
    }
    return `<li class="archive-entry is-event"><span class="entry-index">${item.scene ? "S" + String(item.scene).padStart(3, "0") : "缘"}</span><div>
      <h3>${escapeHtml(item.statement || "关系内容 UNKNOWN")}</h3>
      <p>${escapeHtml(list(item.participants).join(" · ") || "参与者 UNKNOWN")}</p>
      <small>${escapeHtml(item.status || "UNKNOWN")}</small>
    </div></li>`;
  }

  function renderArchiveList(snap) {
    const source = list(snap[archiveTab]);
    const q = archiveQuery.trim().toLowerCase();
    const rows = source
      .filter(item => !q || JSON.stringify(item).toLowerCase().includes(q))
      .slice(0, 40);
    const panel = $("#archive-list");
    const counter = $("#archive-count");
    panel.innerHTML = rows.length
      ? rows.map(archiveEntry).join("")
      : `<li class="empty-state"><b>没有在当前簿册里找到「${escapeHtml(archiveQuery.trim())}」</b>UNKNOWN 不会被自动补写。</li>`;
    counter.textContent = q
      ? `显示 ${fmt(rows.length)} / ${fmt(source.length)}`
      : `显示 ${fmt(Math.min(40, source.length))} / ${fmt(source.length)}`;
  }

  function renderWorld(snap) {
    const tab = TABS.find(t => t.id === archiveTab) || TABS[0];
    const c = snap.counts || {};
    view.innerHTML = `
      <section class="world-intro">
        <div>
          <p class="eyebrow">活态世界档案馆</p>
          <h1>世界档案馆</h1>
          <p>这里不替故事做结论，只收录已发生、被看见、仍未解的痕迹。换一盏灯，看荷园。</p>
        </div>
        <div class="world-seal" aria-label="公开阅读快照">未封卷<small>LIVE ARCHIVE</small></div>
      </section>

      <div class="world-console">
        <div class="archive-tabs" role="tablist" aria-label="档案维度">
          ${TABS.map(t => `<button type="button" role="tab" class="archive-tab" data-archive-tab="${t.id}"
            aria-selected="${t.id === archiveTab}" aria-controls="archive-panel">
            <span class="glyph" aria-hidden="true">${t.glyph}</span>${t.label}
            <span class="tab-n">${fmt(list(snap[t.id]).length)}</span>
          </button>`).join("")}
        </div>
        <label class="archive-search">
          <span aria-hidden="true">⌕</span>
          <span class="visually-hidden">搜索当前簿册</span>
          <input id="archive-search" type="search" placeholder="在当前簿册里找一条线索" value="${escapeHtml(archiveQuery)}">
        </label>
      </div>

      <div class="world-grid">
        <div class="archive-panel" id="archive-panel" role="tabpanel">
          <div class="panel-head">
            <div><p class="eyebrow">${escapeHtml(tab.label)}</p><h2>${escapeHtml(tab.head)}</h2></div>
            <span class="result-count" id="archive-count" aria-live="polite"></span>
          </div>
          <ul class="archive-list" id="archive-list"></ul>
        </div>
        <aside class="world-aside">
          <div class="aside-card">
            <p class="eyebrow">档案说明</p>
            <h2>所见，未必是真</h2>
            <p>公开层只显示已发布快照。证据不足之处保留 UNKNOWN，留给下一轮推演与读者回望。</p>
            <dl>
              <div><dt>人物</dt><dd>${fmt(c.characters)}</dd></div>
              <div><dt>地点</dt><dd>${fmt(c.places)}</dd></div>
              <div><dt>事件</dt><dd>${fmt(c.events)}</dd></div>
              <div><dt>物件</dt><dd>${fmt(c.props_public)}</dd></div>
            </dl>
          </div>
          <div class="aside-card quote-card">
            <span class="mark" aria-hidden="true">“</span>
            <p>你以为看见的是鬼，其实看见的是一个人不肯放下的过去。</p>
          </div>
        </aside>
      </div>`;

    renderArchiveList(snap);

    view.querySelectorAll("[data-archive-tab]").forEach(btn => {
      btn.addEventListener("click", () => {
        archiveTab = btn.dataset.archiveTab;
        archiveQuery = "";
        renderWorld(snap);
        view.querySelector(`[data-archive-tab="${archiveTab}"]`)?.focus();
      });
    });
    $("#archive-search").addEventListener("input", event => {
      archiveQuery = event.target.value;
      renderArchiveList(snap);
    });

    pageTitle("世界档案馆");
    focusMain();
  }

  /* ---------- desk (independent originals) ---------- */

  /* Works carry an optional portrait cover at assets.cover. The title sits
     right beside it, so the image is decorative: empty alt, lazy, fixed
     intrinsic size so the grid never shifts while it loads. */
  function coverArt(work) {
    const src = (work.assets && work.assets.cover) || "";
    if (!src) return `<span class="desk-cover is-empty" aria-hidden="true"></span>`;
    return `<span class="desk-cover"><img src="${escapeHtml(src)}" alt="" loading="lazy" decoding="async" width="600" height="900"></span>`;
  }

  const deskWork = (d, id) => list(d.works).find(w => w.id === id);

  const deskTile = work => `<li><a class="desk-tile" href="#/desk/${encodeURIComponent(work.id)}">
      ${coverArt(work)}
      <span class="desk-body">
        <span class="tone">${escapeHtml(work.tone || "独立稿")}</span>
        <b>《${escapeHtml(work.title)}》</b>
        <small>${escapeHtml(work.logline || "")}</small>
        <span class="foot">${list(work.episodes).length} 集可读${work.status ? ` · ${escapeHtml(work.status)}` : ""}</span>
      </span>
    </a></li>`;

  function renderDesk(d) {
    const works = [...list(d.works)].sort((a, b) => list(b.episodes).length - list(a.episodes).length);
    view.innerHTML = `
      <section class="page-intro">
        <p class="eyebrow">听荷轩 · 独立栏目</p>
        <h1>原创桌</h1>
        <p>${escapeHtml(d.note || "独立稿，不是残荷正史。")}</p>
      </section>
      <ul class="desk-tiles">${works.map(deskTile).join("")}</ul>`;
    pageTitle("原创桌");
    focusMain();
  }

  const packCard = (work, pack) => `<li><a class="pack-card" href="#/desk/${encodeURIComponent(work.id)}/${encodeURIComponent(pack.id)}">
      <span class="pack-mark" aria-hidden="true">${escapeHtml(pack.glyph || "包")}</span>
      <span class="pack-copy">
        <b>${escapeHtml(pack.title)}</b>
        <small>${escapeHtml(pack.summary || "")}</small>
        <em>${escapeHtml(pack.count || "")}</em>
      </span>
    </a></li>`;

  function renderDeskWork(d, workId) {
    const work = deskWork(d, workId);
    if (!work) return renderDesk(d);
    const packs = list(work.packs);
    const graph = work.assets && work.assets.asset_graph;

    view.innerHTML = `
      <section class="work-hero">
        ${coverArt(work)}
        <div class="work-hero-copy">
          <p class="eyebrow">原创桌 · ${escapeHtml(work.tone)}</p>
          <h1>《${escapeHtml(work.title)}》</h1>
          <p class="work-lede">${escapeHtml(work.logline)}</p>
          <p class="meta-line">${list(work.episodes).length} 集 · 人物 ${escapeHtml(list(work.chars).slice(0, 6).join(" · ") || "UNKNOWN")}</p>
          <p><a class="quiet-link" href="#/desk">← 回到原创桌</a></p>
        </div>
      </section>
      ${packs.length ? `<section class="section">
        ${sectionHead("packs-title", "制作资产", "分册入口", `<span class="section-note">身份与空间分开看</span>`)}
        <ul class="pack-grid">${packs.map(p => packCard(work, p)).join("")}</ul>
      </section>` : ""}
      ${graph ? `<section class="section">
        ${sectionHead("graph-entry-title", "连续性索引", "世界观资产图谱", `<a class="quiet-link" href="#/desk/${encodeURIComponent(work.id)}/asset-graph">打开图谱 ↗</a>`)}
        <p class="desk-note">按人物、场景、规则筛选；每个节点与关系都保留证据引用。</p>
      </section>` : ""}
      <section class="section">
        ${sectionHead("eps-title", "正文", `${list(work.episodes).length} 集已编目`, `<a class="quiet-link" href="#/desk">回到原创桌 ↗</a>`)}
        <ol class="catalog">${list(work.episodes).map(ep => `<li class="chapter-card"><a href="#/desk/${encodeURIComponent(work.id)}/${encodeURIComponent(ep.id)}">
          <span class="chapter-no">${escapeHtml((ep.id || "").toUpperCase())}</span>
          <span class="chapter-body">
            <b>${escapeHtml(ep.title)}</b>
            <small class="truncate">${escapeHtml(ep.beat || work.tone || "")}</small>
          </span>
          <span class="chapter-arrow" aria-hidden="true">↗</span>
        </a></li>`).join("")}</ol>
      </section>`;

    pageTitle(`《${work.title}》`);
    focusMain();
  }

  function simpleReader({ kicker, title, meta, html, pager }) {
    view.innerHTML = readerShell({
      where: escapeHtml(title),
      body: `<div class="desk-reader"><p class="chapter-kicker">${escapeHtml(kicker)}</p><h1>${escapeHtml(title)}</h1><p class="meta">${escapeHtml(meta)}</p>${html}</div>`,
      pager,
      toc: false,
    });
    readerCtx = null;
    paintReaderProgress();
    focusMain();
  }

  async function renderDeskPack(d, workId, packId) {
    const work = deskWork(d, workId);
    const pack = work && list(work.packs).find(p => p.id === packId);
    if (!pack) return renderDeskWork(d, workId);
    const payload = await data(`pack-${packId}`, pack.file);
    const back = `#/desk/${encodeURIComponent(workId)}`;
    const sibling = list(work.packs).find(p => p.id !== packId);

    simpleReader({
      kicker: `制作资产 · ${work.tone}`,
      title: payload.title || pack.title,
      meta: "独立稿 · 只锁身份与空间，不替正文抢戏",
      html: payload.html,
      pager: `<a href="${back}"><span aria-hidden="true">←</span> 回到本剧</a>
        <a href="#/desk">原创桌</a>
        <a href="${sibling ? `#/desk/${encodeURIComponent(workId)}/${encodeURIComponent(sibling.id)}` : back}">${escapeHtml(sibling ? sibling.title : "回到本剧")} <span aria-hidden="true">→</span></a>`,
    });
    pageTitle(payload.title || pack.title);
  }

  async function renderDeskEpisode(d, workId, epId) {
    const work = deskWork(d, workId);
    if (!work) return renderDesk(d);
    const eps = list(work.episodes);
    const idx = Math.max(0, eps.findIndex(e => e.id === epId));
    const ep = eps[idx];
    if (!ep) return renderDeskWork(d, workId);
    const payload = await data(`ep-${workId}-${epId}`, ep.file);
    try { localStorage.setItem("tinghe.desk.progress", JSON.stringify({ workId, epId, t: Date.now() })); } catch { /* private mode */ }
    const prev = eps[idx - 1], next = eps[idx + 1];

    simpleReader({
      kicker: `原创桌 · ${work.tone}`,
      title: payload.title,
      meta: `独立稿 · 不是残荷正史 · ${idx + 1} / ${eps.length}`,
      html: payload.html,
      pager: `<a href="${prev ? `#/desk/${encodeURIComponent(workId)}/${encodeURIComponent(prev.id)}` : `#/desk/${encodeURIComponent(workId)}`}"><span aria-hidden="true">←</span> ${prev ? "上一集" : "本剧目录"}</a>
        <a href="#/desk">原创桌</a>
        <a href="${next ? `#/desk/${encodeURIComponent(workId)}/${encodeURIComponent(next.id)}` : `#/desk/${encodeURIComponent(workId)}`}">${next ? "下一集" : "回到本剧"} <span aria-hidden="true">→</span></a>`,
    });
    pageTitle(payload.title);
  }

  /* ---------- asset graph ---------- */

  const GRAPH_TYPES = [["all", "全部"], ["character", "人物"], ["place", "地点"], ["rule", "规则"], ["prop", "道具"], ["scene", "场次"], ["media", "图片资产"]];
  const GRAPH_TYPE_LABEL = { character: "人物", place: "地点", prop: "道具", rule: "规则", scene: "场次", episode: "剧集", media: "图片资产" };
  const GRAPH_EDGE_LABEL = { appears_in: "出现在", happens_at: "发生于", bound_to: "绑定信物", governed_by: "受规则约束", changes: "改变", visualizes: "视觉呈现", continues: "接续", references: "收录" };

  async function renderDeskGraph(d, workId) {
    const work = deskWork(d, workId);
    const src = work && work.assets && work.assets.asset_graph;
    if (!src) return renderDeskWork(d, workId);
    const graph = await data("graph", src);
    const nodes = list(graph.nodes);
    const back = `#/desk/${encodeURIComponent(workId)}`;

    view.innerHTML = `
      <section class="page-intro">
        <p class="eyebrow">《${escapeHtml(work.title)}》 · 连续性索引</p>
        <h1>世界观资产图谱</h1>
        <p>从人物、规则、空间到信物和场次，查看哪些内容相连、依据来自哪里。图谱是剧本与资产包的派生索引，不替剧情做决定。</p>
        <p class="meta-line">${fmt(nodes.length)} 个节点 · ${fmt(list(graph.edges).length)} 条有来源关系</p>
      </section>
      <div class="graph-bar">
        <div class="graph-filters" role="group" aria-label="筛选图谱节点">
          ${GRAPH_TYPES.map(([id, label]) => `<button type="button" class="graph-filter" data-graph-filter="${id}" aria-pressed="${id === "all"}">${label}</button>`).join("")}
        </div>
        <label class="filter-field"><span aria-hidden="true">⌕</span><span class="visually-hidden">搜索图谱</span>
          <input id="graph-search" type="search" placeholder="搜索人物、地点、规则或道具"></label>
      </div>
      <p class="graph-summary" id="graph-summary" aria-live="polite"></p>
      <ul class="graph-nodes" id="graph-nodes"></ul>
      <nav class="pager">
        <a href="${back}"><span aria-hidden="true">←</span> 回到本剧</a>
        <a href="#/desk">原创桌</a>
      </nav>`;

    let active = "all", query = "";
    const draw = () => {
      const shown = nodes.filter(n =>
        (active === "all" || n.type === active) &&
        `${n.name || ""} ${n.status || ""}`.toLowerCase().includes(query));

      $("#graph-nodes").innerHTML = shown.length ? shown.map(node => {
        const links = list(graph.edges)
          .filter(e => e.from === node.id || e.to === node.id)
          .map(e => {
            const otherId = e.from === node.id ? e.to : e.from;
            const other = nodes.find(n => n.id === otherId);
            return `<li><span class="rel">${escapeHtml(GRAPH_EDGE_LABEL[e.type] || e.type)}</span><b>${escapeHtml(other ? other.name : "UNKNOWN")}</b><small>依据：${escapeHtml(e.source_ref || "未标注")}</small></li>`;
          }).join("");
        const refs = list(node.asset_refs);
        return `<li class="graph-node">
          <div class="graph-node-head"><span class="type">${escapeHtml(GRAPH_TYPE_LABEL[node.type] || node.type)}</span><span class="status">${escapeHtml(node.status || "UNKNOWN")}</span></div>
          <h2>${escapeHtml(node.name)}</h2>
          ${refs.length ? `<p class="graph-assets">${refs.map(r => `<span>${escapeHtml(r.split("/").pop())}</span>`).join("")}</p>` : ""}
          ${links ? `<ul class="graph-links">${links}</ul>` : '<p class="graph-empty">暂无已确认关系</p>'}
          <small class="graph-source">来源：${escapeHtml(list(node.source_refs).join(" · ") || "UNKNOWN")}</small>
        </li>`;
      }).join("") : '<li class="empty-state"><b>没有匹配的图谱节点</b>换个筛选条件或关键词。</li>';

      $("#graph-summary").textContent = `显示 ${shown.length} / ${nodes.length} 个节点`;
    };

    view.querySelectorAll("[data-graph-filter]").forEach(btn => btn.addEventListener("click", () => {
      active = btn.dataset.graphFilter;
      view.querySelectorAll("[data-graph-filter]").forEach(b => b.setAttribute("aria-pressed", String(b === btn)));
      draw();
    }));
    $("#graph-search").addEventListener("input", e => { query = e.target.value.trim().toLowerCase(); draw(); });
    draw();
    pageTitle(`世界观资产图谱 · ${work.title}`);
    focusMain();
  }

  /* ---------- header search ---------- */

  const STATUS_CN = { stated: "已记录", inferred: "推断", unknown: "待考" };
  const statusCn = s => STATUS_CN[s] || s || "已记录";

  function wireSearch() {
    const overlay = $("#search-overlay");
    const input = $("#search-input");
    const results = $("#search-results");
    if (!overlay) return;
    let book = null, index = null, loaded = false;

    const close = () => { overlay.hidden = true; };
    const open = async () => {
      overlay.hidden = false;
      input.value = "";
      results.innerHTML = '<p class="search-empty">正在取档案索引…</p>';
      input.focus();
      if (loaded) return draw("");
      const [b, idx] = await Promise.all([loadBook(), loadSearchIndex()]);
      book = b; index = list(idx.entries); loaded = true;
      draw(input.value);
    };

    function draw(q) {
      const needle = q.trim().toLowerCase();
      const groups = [];
      if (book) {
        const hits = book.chapters
          .filter(c => !needle || `${c.title} ${c.place} ${c.time} ${c.preview || ""}`.toLowerCase().includes(needle))
          .slice(0, needle ? 8 : 5);
        if (hits.length) groups.push(["场次", hits.map(c => {
          const cast = castOf(c);
          return {
            glyph: "卷", tag: "章节", name: c.title,
            detail: [c.time, c.place].filter(Boolean).join(" · ") + (cast.length ? ` · ${cast.slice(0, 3).join(" · ")}` : ""),
            href: `#/read/${encodeURIComponent(c.id)}`,
          };
        })]);
      }
      if (index) {
        const byType = { characters: "人物", places: "地点", props: "物件", events: "事件", relationships: "关系" };
        const glyphOf = { characters: "人", places: "地", props: "物", events: "事", relationships: "缘" };
        for (const [type, label] of Object.entries(byType)) {
          const hits = index.filter(e => e.t === type && (!needle || `${e.n} ${e.d}`.toLowerCase().includes(needle))).slice(0, needle ? 5 : 3);
          if (hits.length) groups.push([label, hits.map(e => ({
            glyph: glyphOf[type], tag: statusCn(e.s), name: e.n, detail: e.d, href: "#/world",
          }))]);
        }
      }

      if (!groups.length) {
        results.innerHTML = `<p class="search-empty"><b>没有找到「${escapeHtml(needle)}」</b>换个词，或者只写一个地点或物件名。</p>`;
        return;
      }
      results.innerHTML = groups.map(([label, rows]) => `
        <p class="search-group">${escapeHtml(label)}</p>
        ${rows.map(r => `<a class="search-row" href="${r.href}">
          <span class="glyph" aria-hidden="true">${r.glyph}</span>
          <span class="row-copy"><b>${escapeHtml(r.name)}</b><small>${escapeHtml(r.detail)}</small></span>
          <span class="row-tag">${escapeHtml(r.tag)}</span>
        </a>`).join("")}`).join("");
    }

    input.addEventListener("input", () => draw(input.value));
    overlay.addEventListener("click", event => { if (event.target === overlay) close(); });
    $("#search-open").addEventListener("click", open);
    document.addEventListener("keydown", event => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        overlay.hidden ? open() : close();
      }
    });
    wireSearch.dismiss = close;
  }

  /* ---------- router ---------- */

  const route = () => location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);

  async function render() {
    const [head, a, b] = route();
    setActiveNav(head || "home");
    try {
      if (!head) return await renderHome();
      if (head === "catalog") {
        const book = await loadBook();
        view.innerHTML = "";
        return renderCatalog(book);
      }
      if (head === "read") {
        const book = await loadBook();
        return await renderRead(book, a || lastRead() || "c000");
      }
      if (head === "world") return renderWorld(await loadSnapshot());
      if (head === "desk") {
        const d = await loadDesk();
        if (!a) return renderDesk(d);
        if (b === "asset-graph") return await renderDeskGraph(d, a);
        const work = deskWork(d, a);
        if (work && list(work.packs).some(p => p.id === b)) return await renderDeskPack(d, a, b);
        if (b) return await renderDeskEpisode(d, a, b);
        return renderDeskWork(d, a);
      }
      location.replace("#/");
    } catch (err) {
      errorBox(err);
    }
    promoteCovers();
  }

  window.addEventListener("hashchange", render);
  wireChrome();
  wireSearch();
  render();
})();