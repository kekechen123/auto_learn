#!/usr/bin/env python3
"""Download a curated bibliography with arXiv metadata and resumable validation."""

import argparse
import csv
import hashlib
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
ATOM = {"a": "http://www.w3.org/2005/Atom"}
SESSION = requests.Session()
SESSION.headers["User-Agent"] = "PersonalResearchLibrary/1.0 (50-paper academic collection)"
LAST_ARXIV_REQUEST = 0.0


def get(url, **kwargs):
    global LAST_ARXIV_REQUEST
    for attempt in range(4):
        if "arxiv.org" in url:
            time.sleep(max(0, 3.2 - (time.monotonic() - LAST_ARXIV_REQUEST)))
            LAST_ARXIV_REQUEST = time.monotonic()
        try:
            response = SESSION.get(url, timeout=(20, 150), **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))


def metadata(papers):
    ids = [p["arxiv"] for p in papers if p.get("arxiv")]
    cache = ROOT / "arxiv_metadata.xml"
    if cache.exists() and all(
        any(
            re.sub(r"v\d+$", "", entry.findtext("a:id", "", ATOM).rsplit("/", 1)[-1]) == paper_id
            for entry in ET.fromstring(cache.read_bytes()).findall("a:entry", ATOM)
        )
        for paper_id in ids
    ):
        xml = cache.read_bytes()
    else:
        xml = get(
            "https://export.arxiv.org/api/query",
            params={"id_list": ",".join(ids), "max_results": len(ids)},
        ).content
        ET.fromstring(xml)
        cache.write_bytes(xml)
    entries = {}
    for entry in ET.fromstring(xml).findall("a:entry", ATOM):
        version = entry.findtext("a:id", "", ATOM).rsplit("/", 1)[-1]
        entries[re.sub(r"v\d+$", "", version)] = {
            "title": " ".join(entry.findtext("a:title", "", ATOM).split()),
            "year": int(entry.findtext("a:published", "", ATOM)[:4]),
            "published": entry.findtext("a:published", "", ATOM),
            "updated": entry.findtext("a:updated", "", ATOM),
            "version": version,
            "authors": [a.findtext("a:name", "", ATOM) for a in entry.findall("a:author", ATOM)],
            "abstract": " ".join(entry.findtext("a:summary", "", ATOM).split()),
            "source": f"https://arxiv.org/abs/{version}",
            "pdf": f"https://arxiv.org/pdf/{version}",
        }
    for p in papers:
        if p.get("arxiv"):
            if p["arxiv"] not in entries:
                raise ValueError(f"Missing metadata for {p['key']}: {p['arxiv']}")
            p.update(entries[p["arxiv"]])
    return papers


def validate(path):
    with path.open("rb") as f:
        if not f.read(1024).lstrip().startswith(b"%PDF-"):
            raise ValueError("Not a PDF")
        f.seek(max(0, path.stat().st_size - 4096))
        if b"%%EOF" not in f.read():
            raise ValueError("PDF has no end marker")
    result = {}
    try:
        import pypdf
    except ImportError:
        return result
    reader = pypdf.PdfReader(path)
    result["pages"] = len(reader.pages)
    if not result["pages"]:
        raise ValueError("PDF has no pages")
    result["pdf_title"] = str((reader.metadata or {}).get("/Title", ""))
    result["first_page_text"] = (reader.pages[0].extract_text() or "")[:2500]
    return result


def write_indexes(papers):
    (ROOT / "library.json").write_text(
        json.dumps(papers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    fields = ["number", "key", "year", "title", "category", "arxiv", "version", "path",
              "source", "pdf", "pages", "bytes", "sha256", "status", "note"]
    with (ROOT / "papers.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(papers)
    lines = [
        "# AI Paper Library", "",
        "50 curated papers and original technical reports. arXiv first; official PDFs for exceptions.",
        "",
        "## Important distinctions", "",
        "- GPT-1 and GPT-2 are the original OpenAI reports, obtained from official OpenAI hosting.",
        "- GPT-4o is a system card, not a full architecture/training technical paper.",
        "- InstructGPT is included for the GPT-3.5 / ChatGPT training lineage. It is NOT renamed as a GPT-3.5 paper.",
        "- pi0.6 is represented by the official pi0.6* / RECAP paper, which also discusses the base pi0.6 model.",
        "- This is a curated collection, not an exhaustive or latest-only list of company publications.",
        "",
        "## Reading Paths", "",
        "- LLM: Transformer -> GPT-1/2/3 -> Scaling Laws -> InstructGPT -> GPT-4 -> GPT-4o.",
        "- Vision: LeNet -> AlexNet -> VGG -> ResNet -> ViT -> Swin -> Segment Anything.",
        "- Generation: VAE / GAN -> DDPM -> DDIM -> Score SDE -> Latent Diffusion -> DiT -> Flow Matching.",
        "- Robotics: RT-2 -> pi0 -> pi0.5 -> pi0.6* -> pi0.7.",
        "- Alignment: PPO -> Helpful/Harmless RLHF -> Constitutional AI -> DPO -> Sleeper Agents.",
        "",
        "## Papers", "",
        "| # | Model / topic | Year | Paper | PDF | Source |",
        "|---|---|---|---|---|---|",
    ]
    for p in papers:
        title = p["title"].replace("|", "\\|")
        source = p.get("source", p["pdf"])
        local = f"[PDF]({p['path']})" if p.get("status") == "ok" else "**FAILED**"
        lines.append(f"| {p['number']:02d} | {p['key']} | {p['year']} | {title} | {local} | [original]({source}) |")
    good = [p for p in papers if p.get("status") == "ok"]
    lines += [
        "", "## Download and Validation", "",
        f"- Successful PDFs: {len(good)} / {len(papers)}.",
        f"- Total size: {sum(p.get('bytes', 0) for p in good) / 1024**2:.1f} MiB.",
        "- arxiv_metadata.xml preserves the official metadata response and exact version IDs.",
        "- library.json records authors, abstracts, source URLs, SHA-256, sizes, and validation results.",
        "- papers.csv is UTF-8 with BOM for spreadsheet compatibility.",
        "- Downloads are serial, with at least 3.2 seconds between arXiv request starts, retries, and atomic .part replacement.",
        "- PDF checks: header, end marker, and page parsing when pypdf is installed.",
        "", "Re-run to verify existing files and retry missing downloads:", "",
        "```bash", ".venv/bin/python download_papers.py", "```", "",
        "The local .venv contains the PDF parser. To recreate it:", "",
        "```bash", "python3 -m venv .venv",
        ".venv/bin/python -m pip install requests pypdf fonttools", "```", "",
        "## Acquisition Method", "",
        "- Official arXiv Atom API accepts id_list for a single metadata request covering the bibliography.",
        "- For only 50 known papers, direct PDF requests avoid installing a discovery/crawling stack.",
        "- For corpus-scale acquisition, arXiv offers bulk metadata/full-text access; that is unnecessary here.",
        "- Official API documentation: https://info.arxiv.org/help/api/user-manual.html",
        "- Official bulk access documentation: https://info.arxiv.org/help/bulk_data/index.html", "",
    ]
    (ROOT / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata-only", action="store_true")
    args = parser.parse_args()
    previous = {}
    if (ROOT / "library.json").exists():
        previous = {
            p["key"]: p for p in json.loads((ROOT / "library.json").read_text())
        }
    papers = metadata(json.loads((ROOT / "papers.json").read_text()))
    if len(papers) != 50 or len({p["key"] for p in papers}) != 50:
        raise ValueError("Expected 50 distinct papers")
    for number, p in enumerate(papers, 1):
        p["number"] = number
        p["path"] = f"{p['category']}/{number:02d}_{p['year']}_{p['key']}.pdf"
    if args.metadata_only:
        for p in papers:
            print(f"{p['number']:02d} {p['key']}: {p['title']}", flush=True)
        write_indexes(papers)
        return
    for p in papers:
        path = ROOT / p["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(".pdf.part")
        try:
            if path.exists():
                try:
                    p.update(validate(path))
                except Exception:
                    path.rename(path.with_suffix(".pdf.invalid"))
            source_changed = previous.get(p["key"], {}).get("pdf", p["pdf"]) != p["pdf"]
            if not path.exists() or source_changed:
                with get(p["pdf"], stream=True) as response:
                    with partial.open("wb") as f:
                        for chunk in response.iter_content(1024 * 256):
                            if chunk:
                                f.write(chunk)
                p.update(validate(partial))
                partial.replace(path)
            p.update(validate(path))
            p["bytes"] = path.stat().st_size
            with path.open("rb") as f:
                p["sha256"] = hashlib.file_digest(f, "sha256").hexdigest()
            p["downloaded_at"] = datetime.now(timezone.utc).isoformat()
            p["status"] = "ok"
            print(f"OK {p['number']:02d}/50 {p['key']} {p['bytes'] / 1024**2:.1f} MiB", flush=True)
        except Exception as e:
            p["status"] = "failed"
            p["error"] = str(e)
            print(f"FAILED {p['key']}: {e}", flush=True)
        write_indexes(papers)
    failed = [p["key"] for p in papers if p["status"] != "ok"]
    print(f"Complete: {50 - len(failed)}/50. Failures: {failed}", flush=True)
    sys.exit(bool(failed))


if __name__ == "__main__":
    main()
