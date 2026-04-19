#!/usr/bin/env python3
"""Build daily Arxiv AI digest data and static pages (stdlib-first)."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import escape, unescape
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PAPERS_DIR = DATA_DIR / "papers"
IMAGES_DIR = DATA_DIR / "images"

ARXIV_API = "https://export.arxiv.org/api/query"
ARXIV_QUERY = "cat:cs.AI OR cat:cs.LG OR cat:cs.RO OR cat:cs.HC"
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}

MODULES = {
    "embodied": {
        "label": "具身智能（VLA / 世界模型 / 机器人）",
        "keywords": ["embodied", "robot", "vla", "world model", "manipulation", "navigation", "policy"],
    },
    "llm_agent": {
        "label": "大语言模型与 Agent",
        "keywords": ["llm", "language model", "agent", "alignment", "reasoning", "prompt", "tool"],
    },
}


@dataclass
class Paper:
    paper_id: str
    title: str
    authors: List[str]
    affiliations: List[str]
    summary: str
    summary_sentence: str
    method_summary: str
    conclusion_summary: str
    published_at: str
    updated_at: str
    categories: List[str]
    module: str
    module_label: str
    abs_url: str
    pdf_url: str
    image_url: str


def http_get(url: str, params: dict | None = None, timeout: int = 35) -> str:
    full_url = url if not params else f"{url}?{urlencode(params)}"
    req = Request(full_url, headers={"User-Agent": "arxiv-daily-digest/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")



def short_summary(text: str, limit: int = 420) -> str:
    clean = " ".join(text.split())
    return clean if len(clean) <= limit else clean[: limit - 1].rstrip() + "…"


def naive_summarize(text: str, prefix: str) -> str:
    pieces = re.split(r"(?<=[.!?。])\s+", " ".join(text.split()))
    selected = " ".join(pieces[:2]).strip() or text[:220]
    return f"{prefix}：{short_summary(selected, 260)}"


def generate_model_summary(text: str, cache: Dict[str, str]) -> Dict[str, str]:
    key = str(hash(text))
    if key in cache:
        return json.loads(cache[key])

    method = naive_summarize(text, "方法总结")
    conclusion = naive_summarize(text, "结论总结")

    payload = {"method": method, "conclusion": conclusion}
    cache[key] = json.dumps(payload, ensure_ascii=False)
    return payload


def infer_module(title: str, summary: str) -> str:
    haystack = f"{title} {summary}".lower()
    scores = {m: sum(1 for kw in cfg["keywords"] if kw in haystack) for m, cfg in MODULES.items()}
    return max(scores, key=scores.get)


def normalize_to_https(url: str) -> str:
    if url.startswith("http://"):
        return "https://" + url[len("http://") :]
    return url


def is_generic_arxiv_image(url: str) -> bool:
    lowered = url.lower()
    generic_hints = [
        "arxiv-logo",
        "/static/browse/",
        "paper-image",
        "arxiv_200x100",
    ]
    if any(h in lowered for h in generic_hints):
        return True

    return False


def build_svg_placeholder(arxiv_id: str, title: str) -> str:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    path = IMAGES_DIR / f"{arxiv_id}.svg"
    short_title = escape(short_summary(title, 72))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
<defs><linearGradient id="g" x1="0" x2="1"><stop stop-color="#0f172a"/><stop offset="1" stop-color="#1e293b"/></linearGradient></defs>
<rect width="1200" height="630" fill="url(#g)"/>
<text x="70" y="180" fill="#93c5fd" font-size="36" font-family="Arial">Arxiv Daily Digest</text>
<text x="70" y="270" fill="#f8fafc" font-size="44" font-family="Arial">{escape(arxiv_id)}</text>
<text x="70" y="360" fill="#cbd5e1" font-size="32" font-family="Arial">{short_title}</text>
</svg>'''
    path.write_text(svg, encoding="utf-8")
    return f"data/images/{arxiv_id}.svg"


def extract_fig1_candidate(arxiv_id: str) -> str | None:
    html_urls = [
        f"https://arxiv.org/html/{arxiv_id}",
        f"https://ar5iv.org/html/{arxiv_id}",
    ]

    def find_img(block: str, base_url: str) -> str | None:
        m = re.search(r"<img[^>]+src=['\"]([^'\"]+)['\"]", block, flags=re.I)
        if not m:
            return None
        return normalize_to_https(urljoin(base_url, unescape(m.group(1))))

    for html_url in html_urls:
        try:
            html = http_get(html_url, timeout=20)
        except Exception:
            continue

        figure_blocks = re.findall(r"<figure\b[^>]*>(.*?)</figure>", html, flags=re.S | re.I)
        if not figure_blocks:
            continue

        # 1) Strong preference: caption explicitly says Figure/Fig. 1
        for body in figure_blocks:
            if re.search(r"(figure|fig\.)\s*1\b", body, flags=re.I):
                src = find_img(body, html_url)
                if src and not is_generic_arxiv_image(src):
                    return src

        # 2) Fallback: figure id/class names containing F1 / fig1 / figure-1
        for full in re.findall(r"<figure\b[^>]*>.*?</figure>", html, flags=re.S | re.I):
            if re.search(r"(id|class)=['\"][^'\"]*(fig(?:ure)?[-_. ]?1|f1)[^'\"]*['\"]", full, flags=re.I):
                src = find_img(full, html_url)
                if src and not is_generic_arxiv_image(src):
                    return src

        # 3) Last resort: first non-generic figure image
        for body in figure_blocks:
            src = find_img(body, html_url)
            if src and not is_generic_arxiv_image(src):
                return src

    return None


def extract_image_candidates(abs_url: str, arxiv_id: str) -> List[str]:
    candidates = []

    fig1 = extract_fig1_candidate(arxiv_id)
    if fig1:
        candidates.append(fig1)

    try:
        html = http_get(abs_url, timeout=15)
        og = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
        if og:
            candidates.append(urljoin(abs_url, unescape(og.group(1))))

        for src in re.findall(r'<img[^>]+src="([^"]+)"', html)[:3]:
            candidates.append(urljoin(abs_url, src))
    except Exception:
        pass

    dedup = []
    for item in candidates:
        item = normalize_to_https(item)
        if item not in dedup:
            dedup.append(item)
    return dedup


def persist_image_asset(arxiv_id: str, title: str, abs_url: str) -> str:
    """
    Return a usable image URL without storing binary files in the repo.
    - Prefer remote Fig.1 / og:image candidates.
    - Fallback to local SVG placeholder.
    """
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    for url in extract_image_candidates(abs_url, arxiv_id):
        if not is_generic_arxiv_image(url):
            return url
    return build_svg_placeholder(arxiv_id, title)


def fetch_semantic_scholar_affiliations(arxiv_id: str) -> List[str]:
    url = f"https://api.semanticscholar.org/graph/v1/paper/ARXIV:{arxiv_id}?fields=authors.affiliations"
    try:
        raw = http_get(url, timeout=18)
        payload = json.loads(raw)
        affs = set()
        for author in payload.get("authors", []):
            for aff in author.get("affiliations", []) or []:
                if aff and isinstance(aff, str):
                    affs.add(aff.strip())
        return sorted(a for a in affs if a)[:8]
    except Exception:
        return []


def parse_entries(xml_text: str) -> List[dict]:
    root = ET.fromstring(xml_text)
    entries = []
    for entry in root.findall("atom:entry", NS):
        entry_id = entry.findtext("atom:id", default="", namespaces=NS)
        title = entry.findtext("atom:title", default="", namespaces=NS)
        summary = entry.findtext("atom:summary", default="", namespaces=NS)
        published = entry.findtext("atom:published", default="", namespaces=NS)
        updated = entry.findtext("atom:updated", default="", namespaces=NS)

        authors, affiliations = [], []
        for author in entry.findall("atom:author", NS):
            name = author.findtext("atom:name", default="", namespaces=NS)
            if name:
                authors.append(name)
            aff = author.findtext("arxiv:affiliation", default="", namespaces=NS)
            if aff:
                affiliations.append(aff)

        categories = [c.attrib.get("term", "") for c in entry.findall("atom:category", NS)]

        pdf = f"{entry_id}.pdf"
        for l in entry.findall("atom:link", NS):
            if l.attrib.get("title") == "pdf":
                pdf = l.attrib.get("href", pdf)
                break

        entries.append(
            {
                "entry_id": normalize_to_https(entry_id),
                "title": title,
                "summary": summary,
                "published": published,
                "updated": updated,
                "authors": [a for a in authors if a],
                "affiliations": [a for a in affiliations if a],
                "categories": [c for c in categories if c],
                "pdf": normalize_to_https(pdf),
            }
        )
    return entries


def build_digest(max_results: int) -> Dict[str, object]:
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = DATA_DIR / "summary_cache.json"
    summary_cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}

    try:
        xml = http_get(
            ARXIV_API,
            {
                "search_query": ARXIV_QUERY,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
                "max_results": str(max_results),
            },
            timeout=45,
        )
    except Exception:
        sample_feed = DATA_DIR / "sample_feed.xml"
        if sample_feed.exists():
            xml = sample_feed.read_text(encoding="utf-8")
        else:
            raise

    papers: List[Paper] = []
    for row in parse_entries(xml):
        arxiv_id = row["entry_id"].rsplit("/", 1)[-1]
        module = infer_module(row["title"], row["summary"])
        sums = generate_model_summary(row["summary"], summary_cache)
        papers.append(
            Paper(
                paper_id=arxiv_id,
                title=" ".join(row["title"].split()),
                authors=row["authors"],
                affiliations=row["affiliations"] or fetch_semantic_scholar_affiliations(arxiv_id),
                summary=" ".join(row["summary"].split()),
                summary_sentence=naive_summarize(row["summary"], "摘要首句").replace("摘要首句：", ""),
                method_summary=sums["method"],
                conclusion_summary=sums["conclusion"],
                published_at=row["published"],
                updated_at=row["updated"],
                categories=row["categories"],
                module=module,
                module_label=MODULES[module]["label"],
                abs_url=row["entry_id"],
                pdf_url=row["pdf"],
                image_url=persist_image_asset(arxiv_id, row["title"], row["entry_id"]),
            )
        )

    generated_at = datetime.now(timezone.utc).isoformat()
    day = generated_at[:10]
    digest = {
        "generated_at": generated_at,
        "date": day,
        "stats": {
            "total": len(papers),
            "embodied": sum(1 for p in papers if p.module == "embodied"),
            "llm_agent": sum(1 for p in papers if p.module == "llm_agent"),
        },
        "papers": [asdict(p) for p in papers],
    }

    (PAPERS_DIR / f"{day}.json").write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA_DIR / "latest.json").write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8")
    cache_path.write_text(json.dumps(summary_cache, ensure_ascii=False, indent=2), encoding="utf-8")

    history = sorted(PAPERS_DIR.glob("*.json"), reverse=True)
    index_payload = []
    for file in history[:30]:
        content = json.loads(file.read_text(encoding="utf-8"))
        index_payload.append({"date": content["date"], "generated_at": content["generated_at"], "stats": content["stats"], "file": f"data/papers/{file.name}"})
    (DATA_DIR / "index.json").write_text(json.dumps(index_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-results", type=int, default=36)
    args = parser.parse_args()
    digest = build_digest(args.max_results)
    print(f"Digest built for {digest['date']} with {digest['stats']['total']} papers")


if __name__ == "__main__":
    main()
