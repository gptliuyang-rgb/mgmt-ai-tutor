#!/usr/bin/env python3
"""Build daily Arxiv AI digest data and static pages (stdlib-first)."""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Dict, List
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PAPERS_DIR = DATA_DIR / "papers"

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


def http_post_json(url: str, payload: dict, headers: dict | None = None, timeout: int = 35) -> dict | list:
    merged_headers = {"Content-Type": "application/json"}
    if headers:
        merged_headers.update(headers)
    req = Request(url, data=json.dumps(payload).encode("utf-8"), headers=merged_headers, method="POST")
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
    return json.loads(raw)


def short_summary(text: str, limit: int = 420) -> str:
    clean = " ".join(text.split())
    return clean if len(clean) <= limit else clean[: limit - 1].rstrip() + "…"


def naive_summarize(text: str, prefix: str) -> str:
    pieces = re.split(r"(?<=[.!?。])\s+", " ".join(text.split()))
    selected = " ".join(pieces[:2]).strip() or text[:220]
    return f"{prefix}：{short_summary(selected, 260)}"


def hf_summarize(text: str, token: str) -> str | None:
    endpoint = "https://api-inference.huggingface.co/models/google/flan-t5-small"
    prompt = "Summarize the core method in 2 concise Chinese sentences:\n" + short_summary(text, 1400)
    try:
        resp = http_post_json(
            endpoint,
            {"inputs": prompt, "parameters": {"max_new_tokens": 96, "temperature": 0.1}},
            headers={"Authorization": f"Bearer {token}"},
            timeout=40,
        )
        if isinstance(resp, list) and resp and isinstance(resp[0], dict) and resp[0].get("generated_text"):
            return short_summary(resp[0]["generated_text"], 280)
    except Exception:
        return None
    return None


def generate_model_summary(text: str, cache: Dict[str, str]) -> Dict[str, str]:
    key = str(hash(text))
    if key in cache:
        return json.loads(cache[key])

    method = naive_summarize(text, "方法总结")
    conclusion = naive_summarize(text, "结论总结")

    hf_token = os.getenv("HF_API_TOKEN")
    if hf_token:
        generated = hf_summarize(text, hf_token)
        if generated:
            method = f"方法总结：{generated}"

    payload = {"method": method, "conclusion": conclusion}
    cache[key] = json.dumps(payload, ensure_ascii=False)
    return payload


def infer_module(title: str, summary: str) -> str:
    haystack = f"{title} {summary}".lower()
    scores = {m: sum(1 for kw in cfg["keywords"] if kw in haystack) for m, cfg in MODULES.items()}
    return max(scores, key=scores.get)


def fetch_main_image(arxiv_id: str) -> str:
    fallback = f"https://dummyimage.com/1200x630/111827/ffffff.png&text={quote(arxiv_id)}"
    try:
        html = http_get(f"https://arxiv.org/abs/{arxiv_id}", timeout=15)
        m = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
        if m:
            return unescape(m.group(1))
    except Exception:
        pass
    return fallback




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
                "entry_id": entry_id,
                "title": title,
                "summary": summary,
                "published": published,
                "updated": updated,
                "authors": [a for a in authors if a],
                "affiliations": [a for a in affiliations if a],
                "categories": [c for c in categories if c],
                "pdf": pdf,
            }
        )
    return entries


def build_digest(max_results: int) -> Dict[str, object]:
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
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
                image_url=fetch_main_image(arxiv_id),
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
