#!/usr/bin/env python3
"""Build a self-contained dark-mode HTML reader for the bilingual vocabulary."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VOCABULARY = ROOT / "vocabulary" / "vocabulary.json"
OUTPUT = ROOT / "vocabulary" / "reader.html"

PAGE_SIZE = 50

HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#101412">
  <title>Paperwords | AI English Vocabulary</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #101412;
      --surface: #171d1a;
      --surface-raised: #1c2420;
      --line: #303a34;
      --text: #e8eee9;
      --muted: #99a69d;
      --green: #9cdbb4;
      --green-soft: #223a2d;
      --blue: #a8c9ee;
      --amber: #e7be80;
      --max: 1120px;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 15px/1.65 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    button, input { font: inherit; }
    button { color: inherit; }
    .shell { width: min(var(--max), calc(100% - 40px)); margin: 0 auto; }
    .topbar { border-bottom: 1px solid rgba(153, 166, 157, .16); }
    .topbar-inner {
      min-height: 76px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
    }
    .brand { display: flex; align-items: center; gap: 12px; min-width: 0; }
    .brand-mark {
      width: 36px; height: 36px; display: grid; place-items: center;
      border: 1px solid #547a60; border-radius: 8px;
      color: var(--green); background: #1c2a21; font-weight: 750;
    }
    .brand-name { font-size: 15px; font-weight: 720; letter-spacing: 0; }
    .brand-sub { color: var(--muted); font-size: 12px; }
    .top-count { color: var(--muted); font-size: 13px; white-space: nowrap; }
    main { padding: 42px 0 64px; }
    .intro {
      display: flex; align-items: end; justify-content: space-between;
      gap: 28px; margin-bottom: 28px;
    }
    .eyebrow {
      margin: 0 0 8px; color: var(--green); font-size: 11px;
      font-weight: 750; text-transform: uppercase; letter-spacing: 1.2px;
    }
    h1 { margin: 0; font-size: 30px; line-height: 1.2; font-weight: 690; letter-spacing: 0; }
    .intro-copy { margin: 10px 0 0; color: var(--muted); }
    .progress { min-width: 180px; padding-bottom: 3px; }
    .progress-label { display: flex; justify-content: space-between; gap: 12px; color: var(--muted); font-size: 12px; }
    .progress-track { height: 4px; margin-top: 9px; background: #27302a; border-radius: 2px; overflow: hidden; }
    .progress-fill { height: 100%; width: 0; background: var(--green); transition: width .2s ease; }
    .toolbar {
      display: grid; grid-template-columns: minmax(220px, 1fr) auto auto auto;
      align-items: center; gap: 10px; padding: 12px;
      border: 1px solid var(--line); border-radius: 8px; background: rgba(23, 29, 26, .92);
    }
    .search-wrap { position: relative; }
    .search-icon { position: absolute; left: 13px; top: 8px; color: var(--muted); font-size: 17px; }
    .search {
      width: 100%; height: 40px; padding: 0 38px;
      border: 1px solid var(--line); border-radius: 6px; outline: none;
      background: #111714; color: var(--text);
    }
    .search:focus, .jump-input:focus { border-color: #6a9a78; box-shadow: 0 0 0 2px rgba(156, 219, 180, .12); }
    .search::placeholder { color: #718078; }
    .clear-search {
      position: absolute; right: 7px; top: 5px; width: 30px; height: 30px;
      border: 0; background: transparent; color: var(--muted); cursor: pointer;
    }
    .toolbar-meta { min-width: 100px; color: var(--muted); font-size: 12px; text-align: center; }
    .toolbar-meta strong { color: var(--text); font-weight: 620; }
    .jump { display: flex; align-items: center; gap: 7px; color: var(--muted); font-size: 12px; white-space: nowrap; }
    .jump-input {
      width: 54px; height: 36px; padding: 0 8px; text-align: center;
      border: 1px solid var(--line); border-radius: 6px; outline: none;
      background: #111714; color: var(--text);
    }
    .pager { display: flex; gap: 7px; }
    .button {
      min-height: 38px; display: inline-flex; align-items: center; justify-content: center; gap: 7px;
      padding: 0 12px; border: 1px solid var(--line); border-radius: 6px;
      background: var(--surface-raised); cursor: pointer; transition: border-color .15s, background .15s;
    }
    .button:hover:not(:disabled) { border-color: #64826d; background: #26322b; }
    .button:disabled { opacity: .38; cursor: not-allowed; }
    .button.primary { border-color: #62806b; background: #24382b; color: #d7f4df; }
    .button.primary:hover:not(:disabled) { background: #2b4434; }
    .page-meta {
      display: flex; align-items: center; justify-content: space-between; gap: 16px;
      margin: 21px 2px 10px; color: var(--muted); font-size: 12px;
    }
    .entries { border-top: 1px solid var(--line); }
    .entry {
      display: grid; grid-template-columns: 78px minmax(0, 1fr);
      gap: 18px; padding: 24px 4px 28px; border-bottom: 1px solid var(--line);
      scroll-margin-top: 18px;
    }
    .rank { padding-top: 2px; color: #718078; font-variant-numeric: tabular-nums; font-size: 13px; }
    .entry-main { min-width: 0; }
    .word-line { display: flex; align-items: baseline; flex-wrap: wrap; gap: 9px 14px; }
    .word { font-size: 25px; line-height: 1.25; font-weight: 650; letter-spacing: 0; overflow-wrap: anywhere; }
    .gloss { color: var(--green); font-size: 17px; }
    .stats { display: flex; flex-wrap: wrap; gap: 7px 14px; margin-top: 7px; color: var(--muted); font-size: 12px; }
    .examples { display: grid; gap: 13px; margin-top: 18px; }
    .example {
      padding-left: 14px; border-left: 2px solid #384b3d;
    }
    .example-text { margin: 0; color: #d6dfd8; line-height: 1.7; }
    .example-zh { margin: 5px 0 0; color: #a9b5ac; line-height: 1.65; }
    .example-source {
      display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px;
      margin-top: 7px; color: #7f8e84; font-size: 11px;
    }
    .example-source a { color: var(--blue); text-decoration: none; }
    .example-source a:hover { text-decoration: underline; }
    .empty {
      padding: 72px 16px; border-bottom: 1px solid var(--line);
      color: var(--muted); text-align: center;
    }
    .bottom-pager { display: flex; justify-content: center; gap: 8px; padding-top: 24px; }
    @media (max-width: 760px) {
      .shell { width: min(100% - 28px, var(--max)); }
      .topbar-inner { min-height: 64px; }
      main { padding-top: 30px; }
      .intro { align-items: start; flex-direction: column; gap: 18px; margin-bottom: 22px; }
      h1 { font-size: 26px; }
      .progress { width: 100%; }
      .toolbar { grid-template-columns: 1fr auto; gap: 9px; padding: 10px; }
      .search-wrap { grid-column: 1 / -1; }
      .toolbar-meta { text-align: left; }
      .jump { justify-self: end; }
      .pager { grid-column: 1 / -1; justify-content: space-between; }
      .pager .button { flex: 1; }
      .entry { grid-template-columns: 42px minmax(0, 1fr); gap: 9px; padding: 21px 0 24px; }
      .word { font-size: 23px; }
      .gloss { font-size: 16px; }
      .page-meta { align-items: start; flex-direction: column; gap: 3px; }
    }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; }
    }
  </style>
</head>
<body>
  <header class="topbar">
    <div class="shell topbar-inner">
      <div class="brand">
        <div class="brand-mark">P</div>
        <div>
          <div class="brand-name">Paperwords</div>
          <div class="brand-sub">AI 英语论文词本</div>
        </div>
      </div>
      <div class="top-count"><span id="total-count">2,500</span> 个词 · 50 篇论文</div>
    </div>
  </header>
  <main class="shell">
    <section class="intro">
      <div>
        <p class="eyebrow">RESEARCH ENGLISH · FREQUENCY INDEX</p>
        <h1>读论文，积累真正遇到的词</h1>
        <p class="intro-copy">2,500 WORDS　·　50 PAPERS　·　ENGLISH / 中文</p>
      </div>
      <div class="progress">
        <div class="progress-label"><span>阅读进度</span><span id="progress-label">第 1 页 / 50</span></div>
        <div class="progress-track"><div class="progress-fill" id="progress-fill"></div></div>
      </div>
    </section>

    <section class="toolbar" aria-label="词本控制">
      <label class="search-wrap">
        <span class="search-icon" aria-hidden="true">⌕</span>
        <input class="search" id="search" type="search" placeholder="搜索英文、中文释义或例句" autocomplete="off">
        <button class="clear-search" id="clear-search" type="button" title="清除搜索" aria-label="清除搜索" hidden>×</button>
      </label>
      <div class="toolbar-meta" id="result-count"><strong>1–50</strong> / 2,500</div>
      <label class="jump">跳至
        <input class="jump-input" id="jump" type="number" min="1" max="50" value="1" aria-label="跳转到页码">
        <span id="jump-total">/ 50</span>
      </label>
      <nav class="pager" aria-label="分页">
        <button class="button" id="previous" type="button" title="上一页（←）">← 上一页</button>
        <button class="button primary" id="next" type="button" title="下一页（→）">下一页 →</button>
      </nav>
    </section>

    <div class="page-meta">
      <span id="page-range">词频排名 1–50</span>
      <span>ENGLISH / 中文</span>
    </div>
    <section class="entries" id="entries" aria-live="polite"></section>
    <nav class="bottom-pager" aria-label="底部分页">
      <button class="button" id="previous-bottom" type="button">← 上一页</button>
      <button class="button primary" id="next-bottom" type="button">下一页 →</button>
    </nav>
  </main>
  <script id="vocabulary-data" type="application/json">__VOCABULARY_JSON__</script>
  <script>
    (() => {
      const allEntries = JSON.parse(document.getElementById("vocabulary-data").textContent);
      const pageSize = 50;
      const params = new URLSearchParams(location.search);
      const search = document.getElementById("search");
      const clearSearch = document.getElementById("clear-search");
      const entriesNode = document.getElementById("entries");
      const jump = document.getElementById("jump");
      let page = Math.max(1, Number.parseInt(params.get("page") || "1", 10) || 1);
      let query = "";
      let filtered = allEntries;

      const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      })[char]);
      const totalPages = () => Math.max(1, Math.ceil(filtered.length / pageSize));

      function updateControls() {
        const pages = totalPages();
        page = Math.min(page, pages);
        const start = filtered.length ? (page - 1) * pageSize + 1 : 0;
        const end = Math.min(page * pageSize, filtered.length);
        document.getElementById("total-count").textContent = allEntries.length.toLocaleString();
        document.getElementById("result-count").innerHTML =
          `<strong>${start.toLocaleString()}–${end.toLocaleString()}</strong> / ${filtered.length.toLocaleString()}`;
        document.getElementById("page-range").textContent =
          query ? `搜索结果 ${start.toLocaleString()}–${end.toLocaleString()}` :
            `词频排名 ${filtered.length ? filtered[start - 1].rank.toLocaleString() : 0}–${filtered.length ? filtered[end - 1].rank.toLocaleString() : 0}`;
        document.getElementById("progress-label").textContent = `第 ${page} 页 / ${pages}`;
        document.getElementById("progress-fill").style.width = `${(page / pages) * 100}%`;
        jump.max = String(pages);
        jump.value = String(page);
        document.getElementById("jump-total").textContent = `/ ${pages}`;
        const atStart = page <= 1;
        const atEnd = page >= pages;
        for (const id of ["previous", "previous-bottom"]) document.getElementById(id).disabled = atStart;
        for (const id of ["next", "next-bottom"]) document.getElementById(id).disabled = atEnd;
        clearSearch.hidden = !query;
        const params = new URLSearchParams();
        if (page > 1) params.set("page", String(page));
        if (query) params.set("q", query);
        history.replaceState(null, "", `${location.pathname}${params.size ? `?${params}` : ""}`);
      }

      function renderEntry(entry) {
        const examples = (entry.examples || []).map((example, index) => {
          const pages = (example.pages || []).join(", ");
          const paperPath = `../${example.pdf_path}#page=${example.pages?.[0] || 1}`;
          const sourceLabel = `${example.paper_key} · PDF p. ${pages}`;
          return `<article class="example">
            <p class="example-text">${escapeHtml(example.text)}</p>
            ${example.translation_zh ? `<p class="example-zh">${escapeHtml(example.translation_zh)}</p>` : ""}
            <div class="example-source">
              <span>例句 ${index + 1}</span>
              <a href="${escapeHtml(paperPath)}" target="_blank" rel="noopener">${escapeHtml(sourceLabel)} ↗</a>
              <span>ID ${escapeHtml(example.id)}</span>
            </div>
          </article>`;
        }).join("");
        return `<article class="entry" id="word-${entry.rank}">
          <div class="rank">${String(entry.rank).padStart(4, "0")}</div>
          <div class="entry-main">
            <div class="word-line">
              <span class="word">${escapeHtml(entry.word)}</span>
              <span class="gloss">${escapeHtml(entry.word_zh || "")}</span>
            </div>
            <div class="stats">
              <span>出现 ${Number(entry.frequency).toLocaleString()} 次</span>
              <span>见于 ${entry.paper_count} 篇论文</span>
            </div>
            <div class="examples">${examples}</div>
          </div>
        </article>`;
      }

      function render() {
        const start = (page - 1) * pageSize;
        const visible = filtered.slice(start, start + pageSize);
        entriesNode.innerHTML = visible.length
          ? visible.map(renderEntry).join("")
          : `<div class="empty">没有找到匹配的词条。试试英文单词或中文释义。</div>`;
        updateControls();
      }

      function setPage(nextPage, scroll = true) {
        page = Math.max(1, Math.min(totalPages(), nextPage));
        render();
        if (scroll) window.scrollTo({ top: 0, behavior: "smooth" });
      }

      function setQuery(value) {
        query = value.trim().toLocaleLowerCase();
        filtered = query ? allEntries.filter((entry) => {
          const haystack = [
            entry.word, entry.word_zh,
            ...(entry.examples || []).flatMap((example) => [example.text, example.translation_zh, example.paper_key])
          ].join(" ").toLocaleLowerCase();
          return haystack.includes(query);
        }) : allEntries;
        page = 1;
        render();
      }

      document.getElementById("previous").addEventListener("click", () => setPage(page - 1));
      document.getElementById("next").addEventListener("click", () => setPage(page + 1));
      document.getElementById("previous-bottom").addEventListener("click", () => setPage(page - 1));
      document.getElementById("next-bottom").addEventListener("click", () => setPage(page + 1));
      jump.addEventListener("change", () => setPage(Number.parseInt(jump.value, 10) || 1));
      search.addEventListener("input", () => setQuery(search.value));
      clearSearch.addEventListener("click", () => {
        search.value = "";
        setQuery("");
        search.focus();
      });
      document.addEventListener("keydown", (event) => {
        if (event.altKey || event.ctrlKey || event.metaKey) return;
        if (event.key === "/" && document.activeElement !== search) {
          event.preventDefault();
          search.focus();
        } else if (event.key === "Escape" && document.activeElement === search) {
          search.value = "";
          setQuery("");
          search.blur();
        } else if (event.key === "ArrowLeft" && document.activeElement !== search) {
          setPage(page - 1);
        } else if (event.key === "ArrowRight" && document.activeElement !== search) {
          setPage(page + 1);
        }
      });

      search.value = params.get("q") || "";
      query = search.value.trim().toLocaleLowerCase();
      if (query) {
        filtered = allEntries.filter((entry) =>
          [entry.word, entry.word_zh, ...(entry.examples || []).flatMap((example) =>
            [example.text, example.translation_zh, example.paper_key]
          )].join(" ").toLocaleLowerCase().includes(query)
        );
      }
      page = Math.min(page, totalPages());
      render();
    })();
  </script>
</body>
</html>
"""


def main():
    entries = json.loads(VOCABULARY.read_text(encoding="utf-8"))
    data = json.dumps(entries, ensure_ascii=False, separators=(",", ":"))
    safe_data = data.replace("</", "<\\/")
    OUTPUT.write_text(HTML.replace("__VOCABULARY_JSON__", safe_data), encoding="utf-8")
    print(f"Wrote {OUTPUT} ({len(entries)} words, {PAGE_SIZE} per page).")


if __name__ == "__main__":
    main()
