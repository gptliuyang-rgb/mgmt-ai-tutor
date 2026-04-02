const DATA_INDEX_URL = "./data/index.json";
const LATEST_URL = "./data/latest.json";

const byId = (id) => document.getElementById(id);

function safeDate(iso) {
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

function getStore(key, fallback = {}) {
  try {
    return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback));
  } catch {
    return fallback;
  }
}

function setStore(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

async function loadIndexPage() {
  const meta = byId("meta");
  if (!meta) return;

  const [indexRes, latestRes] = await Promise.all([fetch(DATA_INDEX_URL), fetch(LATEST_URL)]);
  const index = await indexRes.json();
  const latest = await latestRes.json();

  meta.textContent = `最近更新：${safeDate(latest.generated_at)} | 共 ${latest.stats.total} 篇`;

  const dateSelect = byId("dateSelect");
  index.forEach((entry) => {
    const opt = document.createElement("option");
    opt.value = entry.file;
    opt.textContent = `${entry.date} (${entry.stats.total} 篇)`;
    dateSelect.appendChild(opt);
  });

  const renderByFile = async (file) => {
    const digest = await fetch(`./${file}`).then((r) => r.json());
    renderPaperLists(digest.papers);
  };

  await renderByFile(index[0].file);
  dateSelect.addEventListener("change", (e) => renderByFile(e.target.value));
  byId("moduleFilter").addEventListener("change", () => renderPaperLists(latest.papers, true));
}

function makeCard(paper) {
  const tpl = byId("paperTpl");
  const node = tpl.content.cloneNode(true);
  const likes = getStore("likes", {});
  const favs = getStore("favorites", {});

  node.querySelector(".cover").src = paper.image_url;
  node.querySelector(".title").textContent = paper.title;
  node.querySelector(".aff").textContent = `作者：${paper.authors.join(", ")} | 单位：${paper.affiliations?.join("; ") || "未公开"}`;
  node.querySelector(".summary").textContent = paper.summary_sentence;

  const tags = node.querySelector(".tags");
  [paper.module_label, ...paper.categories.slice(0, 3)].forEach((t) => {
    const span = document.createElement("span");
    span.className = "tag";
    span.textContent = t;
    tags.appendChild(span);
  });

  const detailLink = node.querySelector(".detail-link");
  detailLink.href = `./paper.html?id=${paper.paper_id}`;
  const pdfLink = node.querySelector(".pdf-link");
  pdfLink.href = paper.pdf_url;

  const likeBtn = node.querySelector(".like-btn");
  const likeCount = likeBtn.querySelector("span");
  likeCount.textContent = likes[paper.paper_id] || 0;
  likeBtn.addEventListener("click", () => {
    likes[paper.paper_id] = (likes[paper.paper_id] || 0) + 1;
    setStore("likes", likes);
    likeCount.textContent = likes[paper.paper_id];
  });

  const favBtn = node.querySelector(".fav-btn");
  favBtn.textContent = favs[paper.paper_id] ? "⭐ 已收藏" : "⭐ 收藏";
  favBtn.addEventListener("click", () => {
    favs[paper.paper_id] = !favs[paper.paper_id];
    setStore("favorites", favs);
    favBtn.textContent = favs[paper.paper_id] ? "⭐ 已收藏" : "⭐ 收藏";
  });

  return node;
}

function renderPaperLists(papers, filterFromLatest = false) {
  const filter = byId("moduleFilter").value;
  const targetPapers = filterFromLatest
    ? papers.filter((p) => (filter === "all" ? true : p.module === filter))
    : papers;

  const embodied = byId("embodiedList");
  const llm = byId("llmList");
  embodied.innerHTML = "";
  llm.innerHTML = "";

  targetPapers.forEach((p) => {
    const card = makeCard(p);
    if (p.module === "embodied") embodied.appendChild(card);
    else llm.appendChild(card);
  });
}

async function loadDetailPage() {
  const detailRoot = byId("paperDetail");
  if (!detailRoot) return;

  const paperId = new URLSearchParams(location.search).get("id");
  const latest = await fetch(LATEST_URL).then((r) => r.json());
  const paper = latest.papers.find((p) => p.paper_id === paperId) || latest.papers[0];

  detailRoot.innerHTML = `
    <h1>${paper.title}</h1>
    <p><strong>作者：</strong>${paper.authors.join(", ")}</p>
    <p><strong>单位：</strong>${paper.affiliations?.join("; ") || "未公开"}</p>
    <p><strong>发布时间：</strong>${safeDate(paper.published_at)}</p>
    <img class="cover-detail" src="${paper.image_url}" alt="${paper.title}" />
    <section><h3>原始摘要</h3><p>${paper.summary}</p></section>
    <section class="highlight"><h3>方法总结</h3><p>${paper.method_summary}</p></section>
    <section class="highlight"><h3>结论总结</h3><p>${paper.conclusion_summary}</p></section>
    <p><a href="${paper.pdf_url}" target="_blank" rel="noopener">查看原文 PDF</a></p>
  `;

  injectGiscus(paperId || paper.paper_id, paper.title);
}

function injectGiscus(term, title) {
  const root = byId("giscus");
  if (!root) return;

  const cfg = {
    repo: "<YOUR_GITHUB_NAME>/<YOUR_REPO>",
    repoId: "<YOUR_REPO_ID>",
    category: "General",
    categoryId: "<YOUR_CATEGORY_ID>",
  };

  const script = document.createElement("script");
  script.src = "https://giscus.app/client.js";
  script.crossOrigin = "anonymous";
  script.async = true;
  script.setAttribute("data-repo", cfg.repo);
  script.setAttribute("data-repo-id", cfg.repoId);
  script.setAttribute("data-category", cfg.category);
  script.setAttribute("data-category-id", cfg.categoryId);
  script.setAttribute("data-mapping", "specific");
  script.setAttribute("data-term", term);
  script.setAttribute("data-strict", "0");
  script.setAttribute("data-reactions-enabled", "1");
  script.setAttribute("data-emit-metadata", "1");
  script.setAttribute("data-input-position", "top");
  script.setAttribute("data-theme", "light");
  script.setAttribute("data-lang", "zh-CN");
  root.appendChild(script);
}

loadIndexPage();
loadDetailPage();
