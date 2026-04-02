const DATA_INDEX_URL = "./data/index.json";
const LATEST_URL = "./data/latest.json";

const byId = (id) => document.getElementById(id);
let loadedDigest = null;
let loadedHistory = [];

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

function placeholderDataUri(paperId = "paper") {
  const text = encodeURIComponent(paperId);
  return `data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='800' height='450'><rect width='100%25' height='100%25' fill='%23e2e8f0'/><text x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' fill='%23475569' font-size='24' font-family='Arial'>${text}</text></svg>`;
}

function resolveImageUrl(rawUrl, paperId) {
  const url = (rawUrl || "").trim();
  if (!url) return placeholderDataUri(paperId);
  if (url.startsWith("/static/")) return `https://arxiv.org${url}`;
  if (url.startsWith("http://")) return `https://${url.slice(7)}`;
  return url;
}

function applyFilter(papers) {
  const filterEl = byId("moduleFilter");
  const filter = filterEl ? filterEl.value : "all";
  return papers.filter((p) => (filter === "all" ? true : p.module === filter));
}

async function loadIndexPage() {
  const meta = byId("meta");
  if (!meta) return;

  const [indexRes, latestRes] = await Promise.all([fetch(DATA_INDEX_URL), fetch(LATEST_URL)]);
  loadedHistory = await indexRes.json();
  const latest = await latestRes.json();

  meta.textContent = `最近更新：${safeDate(latest.generated_at)} | 共 ${latest.stats.total} 篇`;

  const dateSelect = byId("dateSelect");
  loadedHistory.forEach((entry) => {
    const opt = document.createElement("option");
    opt.value = entry.file;
    opt.textContent = `${entry.date} (${entry.stats.total} 篇)`;
    dateSelect.appendChild(opt);
  });

  const renderByFile = async (file) => {
    loadedDigest = await fetch(`./${file}`).then((r) => r.json());
    renderPaperLists(applyFilter(loadedDigest.papers));
  };

  if (loadedHistory.length > 0) {
    await renderByFile(loadedHistory[0].file);
  } else {
    loadedDigest = latest;
    renderPaperLists(applyFilter(loadedDigest.papers));
  }

  dateSelect.addEventListener("change", (e) => renderByFile(e.target.value));
  byId("moduleFilter").addEventListener("change", () => {
    if (loadedDigest) renderPaperLists(applyFilter(loadedDigest.papers));
  });
}

function makeCard(paper) {
  const tpl = byId("paperTpl");
  const node = tpl.content.cloneNode(true);
  const likes = getStore("likes", {});
  const favs = getStore("favorites", {});

  const cover = node.querySelector(".cover");
  cover.src = resolveImageUrl(paper.image_url, paper.paper_id);
  cover.onerror = () => {
    cover.onerror = null;
    cover.src = placeholderDataUri(paper.paper_id);
  };
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

function renderPaperLists(papers) {
  const embodied = byId("embodiedList");
  const llm = byId("llmList");
  embodied.innerHTML = "";
  llm.innerHTML = "";

  papers.forEach((p) => {
    const card = makeCard(p);
    if (p.module === "embodied") embodied.appendChild(card);
    else llm.appendChild(card);
  });
}

async function loadDetailPage() {
  const detailRoot = byId("paperDetail");
  if (!detailRoot) return;

  const paperId = new URLSearchParams(location.search).get("id");
  const index = await fetch(DATA_INDEX_URL).then((r) => r.json());

  let paper = null;
  for (const item of index) {
    const digest = await fetch(`./${item.file}`).then((r) => r.json());
    paper = digest.papers.find((p) => p.paper_id === paperId);
    if (paper) break;
  }

  if (!paper) {
    const latest = await fetch(LATEST_URL).then((r) => r.json());
    paper = latest.papers[0];
  }

  detailRoot.innerHTML = `
    <h1>${paper.title}</h1>
    <p><strong>作者：</strong>${paper.authors.join(", ")}</p>
    <p><strong>单位：</strong>${paper.affiliations?.join("; ") || "未公开"}</p>
    <p><strong>发布时间：</strong>${safeDate(paper.published_at)}</p>
    <img class="cover-detail" src="${resolveImageUrl(paper.image_url, paper.paper_id)}" alt="${paper.title}" />
    <section><h3>原始摘要</h3><p>${paper.summary}</p></section>
    <section class="highlight"><h3>方法总结</h3><p>${paper.method_summary}</p></section>
    <section class="highlight"><h3>结论总结</h3><p>${paper.conclusion_summary}</p></section>
    <p><a href="${paper.pdf_url}" target="_blank" rel="noopener">查看原文 PDF</a></p>
  `;

  const detailCover = detailRoot.querySelector(".cover-detail");
  if (detailCover) {
    detailCover.onerror = () => {
      detailCover.onerror = null;
      detailCover.src = placeholderDataUri(paper.paper_id);
    };
  }

  injectComments(paperId || paper.paper_id);
}

function injectComments(term) {
  const root = byId("giscus");
  if (!root) return;

  // Default to utterances so comments can work with GitHub login
  // without repo/category IDs. Install app: https://github.com/apps/utterances
  const script = document.createElement("script");
  script.src = "https://utteranc.es/client.js";
  script.setAttribute("repo", "gptliuyang-rgb/mgmt-ai-tutor");
  script.setAttribute("issue-term", term || "pathname");
  script.setAttribute("label", "comment");
  script.setAttribute("theme", "github-light");
  script.setAttribute("crossorigin", "anonymous");
  script.async = true;
  root.appendChild(script);
}

loadIndexPage();
loadDetailPage();
