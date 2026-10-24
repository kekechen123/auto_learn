#!/usr/bin/env python3
"""Build ranked English vocabulary notebooks from the local PDF bibliography."""

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import nltk
import pymupdf
from nltk.tokenize import PunktTokenizer

ROOT = Path(__file__).resolve().parent
EXTRACTOR_VERSION = 2
WORD_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]+(?:'[A-Za-z]+)?(?![A-Za-z0-9])")
URL_RE = re.compile(r"(?:https?://|www\.)[^\s]+|[\w.+-]+@[\w.-]+\.\w+", re.I)
HYPHEN_PREFIXES = {
    "self", "pre", "post", "fine", "multi", "cross", "task", "few", "zero",
    "high", "low", "long", "short", "large", "small", "real", "end", "non",
    "semi", "co", "re", "well", "time", "word", "text", "image", "language",
    "vision", "attention", "model", "data", "human", "test", "training",
    "open", "closed", "score", "flow", "policy", "reward", "state", "of",
    "to", "in", "out", "on", "two", "three", "single", "double", "full",
}


def normalize_text(text):
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(str.maketrans({
        "\u2019": "'", "\u2018": "'", "\u00ad": "", "\u2010": "-",
        "\u2011": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-",
    }))
    text = "".join(c for c in text if c in "\n\t" or unicodedata.category(c) != "Cc")

    def unwrap(match):
        left, right = match.groups()
        separator = "-" if left.lower() in HYPHEN_PREFIXES else ""
        return left + separator + right

    text = re.sub(r"([A-Za-z]+)-[ \t]*\n[ \t]*([a-z]+)", unwrap, text)
    return re.sub(r"\s+", " ", text).strip()


def tokens(text):
    text = URL_RE.sub(" ", text)
    for match in WORD_RE.finditer(text):
        word = match.group().lower()
        if word.endswith("'s"):
            word = word[:-2]
        if len(word) > 1 or word in {"a", "i"}:
            yield word


def readable_ratio(text):
    nonspace = [c for c in text if not c.isspace()]
    if not nonspace:
        return 1.0
    return sum(c.isascii() and (c.isalnum() or c in ".,;:()[]'-/!?%+=<>\"") for c in nonspace) / len(nonspace)


def reading_order(blocks, width):
    """Read each full-width band, with left column before right column."""
    middle = width / 2
    left = [b for b in blocks if b["bbox"][2] <= middle + 12]
    right = [b for b in blocks if b["bbox"][0] >= middle - 12]
    if len(left) < 2 or len(right) < 2:
        return sorted(blocks, key=lambda b: (b["bbox"][1], b["bbox"][0]))
    spanning = [b for b in blocks if b not in left and b not in right]
    ordered = []
    pending = [b for b in blocks if b not in spanning]
    for full in sorted(spanning, key=lambda b: b["bbox"][1]):
        before = [b for b in pending if b["bbox"][1] < full["bbox"][1]]
        ordered.extend(sorted(before, key=lambda b: (b["bbox"][0] >= middle - 12, b["bbox"][1])))
        pending = [b for b in pending if b not in before]
        ordered.append(full)
    ordered.extend(sorted(pending, key=lambda b: (b["bbox"][0] >= middle - 12, b["bbox"][1])))
    return ordered


def pdf_blocks(page):
    blocks = []
    for raw in page.get_text("dict")["blocks"]:
        if raw["type"] != 0:
            continue
        lines = []
        for line in raw["lines"]:
            # Vertical arXiv stamps are not part of the paper prose.
            if abs(line.get("dir", (1, 0))[1]) > 0.5:
                continue
            lines.append("".join(span["text"] for span in line["spans"]))
        text = normalize_text("\n".join(lines))
        if text:
            blocks.append({"bbox": list(raw["bbox"]), "text": text})
    return reading_order(blocks, page.rect.width)


def ocr_blocks(page, executable, tessdata):
    with tempfile.TemporaryDirectory(prefix="vocabulary-ocr-") as tmp:
        image = Path(tmp) / "page.png"
        page.get_pixmap(dpi=240, colorspace=pymupdf.csRGB).save(image)
        env = dict(os.environ, OMP_THREAD_LIMIT="1")
        command = [
            executable, str(image), "stdout", "-l", "eng", "--psm", "3",
            "--tessdata-dir", str(tessdata), "-c", "tessedit_create_tsv=1",
        ]
        result = subprocess.run(command, capture_output=True, text=True, env=env, check=True, timeout=180)
    rows = csv.DictReader(result.stdout.splitlines(), delimiter="\t", quoting=csv.QUOTE_NONE)
    grouped = defaultdict(list)
    scale = 72 / 240
    for row in rows:
        if row["level"] == "5" and row.get("text", "").strip():
            grouped[row["block_num"]].append(row)
    blocks = []
    for words in grouped.values():
        lines = defaultdict(list)
        for word in words:
            lines[(word["par_num"], word["line_num"])].append(word["text"])
        text = normalize_text("\n".join(" ".join(line) for line in lines.values()))
        x0 = min(int(w["left"]) for w in words) * scale
        y0 = min(int(w["top"]) for w in words) * scale
        x1 = max(int(w["left"]) + int(w["width"]) for w in words) * scale
        y1 = max(int(w["top"]) + int(w["height"]) for w in words) * scale
        blocks.append({"bbox": [x0, y0, x1, y1], "text": text})
    return reading_order(blocks, page.rect.width)


def extract_paper(job):
    paper, cache_dir, executable, tessdata, force = job
    path = ROOT / paper["path"]
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    cache_path = Path(cache_dir) / f"{paper['number']:02d}_{paper['key']}.json"
    cached = {}
    if cache_path.exists() and not force:
        cached = json.loads(cache_path.read_text())
        if cached.get("sha256") == digest and cached.get("extractor_version") == EXTRACTOR_VERSION:
            return cached
    pages = []
    with pymupdf.open(path) as document:
        for number, page in enumerate(document, 1):
            blocks = pdf_blocks(page)
            text = " ".join(b["text"] for b in blocks)
            # Broken font encodings can produce abundant, but unusable, text.
            use_ocr = (
                paper["key"] == "LeNet_CNN" or readable_ratio(text) < 0.72
                or (len(text) < 50 and bool(page.get_images()))
            )
            if use_ocr:
                if not executable or not tessdata:
                    raise RuntimeError(f"{paper['key']} page {number} needs Tesseract OCR")
                old_pages = cached.get("pages", [])
                if (
                    not force and cached.get("sha256") == digest
                    and number <= len(old_pages) and old_pages[number - 1]["method"] == "ocr"
                ):
                    blocks = old_pages[number - 1]["blocks"]
                else:
                    blocks = ocr_blocks(page, executable, tessdata)
            pages.append({
                "page": number, "width": page.rect.width, "height": page.rect.height,
                "method": "ocr" if use_ocr else "text", "blocks": blocks,
            })
    # Remove only repeated short blocks in page margins, plus bare page numbers.
    repeated = Counter()
    for page in pages:
        repeated.update(set(
            b["text"] for b in page["blocks"]
            if len(b["text"]) < 160 and
            (b["bbox"][3] < page["height"] * 0.08 or b["bbox"][1] > page["height"] * 0.92)
        ))
    for page in pages:
        kept = []
        for b in page["blocks"]:
            margin = b["bbox"][3] < page["height"] * 0.08 or b["bbox"][1] > page["height"] * 0.92
            if re.fullmatch(r"\d{1,4}", b["text"]) or (margin and repeated[b["text"]] >= 3):
                continue
            kept.append(b)
        page["blocks"] = kept
    result = {
        "paper": paper, "sha256": digest, "extractor_version": EXTRACTOR_VERSION,
        "pages": pages,
    }
    cache_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def sentence_quality(text):
    words = list(tokens(text))
    if len(words) < 6 or len(text) > 1200 or len(text) < 30:
        return None
    if not re.search(r'[.!?]["\')\]]*$', text):
        return None
    if not re.match(r'^[\s"\'(\[]*[A-Z]', text) or readable_ratio(text) < 0.88:
        return None
    if URL_RE.search(text) or len(re.findall(r"\[\d", text)) > 3:
        return None
    if re.match(r"^(?:Table|Figure|Fig\.|References|Bibliography)\b", text) or ".." in text:
        return None
    # Prose should not primarily consist of numeric table cells or equations.
    if sum(c.isalpha() for c in text) / len(text) < 0.62:
        return None
    return abs(len(words) - 23) + text.count("=") * 15 + text.count("[") * 3


def sentence_records(extracted, tokenizer):
    paper = extracted["paper"]
    records = []
    pending_text = ""
    pending_segments = []
    counter = 0

    def flush():
        nonlocal pending_text, pending_segments, counter
        if not pending_text:
            return
        for start, end in tokenizer.span_tokenize(pending_text):
            text = pending_text[start:end].strip()
            score = sentence_quality(text)
            if score is None:
                continue
            segments = [s for s in pending_segments if s["end"] > start and s["start"] < end]
            counter += 1
            records.append({
                "id": f"P{paper['number']:02d}-S{counter:05d}",
                "paper_number": paper["number"], "paper_key": paper["key"],
                "paper_title": paper["title"], "pdf_path": paper["path"],
                "pages": sorted({s["page"] for s in segments}),
                "blocks": [{"page": s["page"], "block": s["block"]} for s in segments],
                "ocr": any(s["ocr"] for s in segments),
                "text": text, "score": score + (20 if any(s["ocr"] for s in segments) else 0),
            })
        pending_text = ""
        pending_segments = []

    for page in extracted["pages"]:
        for block_number, block in enumerate(page["blocks"], 1):
            text = block["text"]
            # Short headings/table labels are counted, but not merged into examples.
            if len(list(tokens(text))) < 5 or re.fullmatch(r"[\d.\s]*[A-Z][^.!?]{0,65}", text):
                flush()
                continue
            if pending_text and (re.search(r'[.!?]["\')\]]*$', pending_text) or len(pending_text) > 3000):
                flush()
            start = len(pending_text) + bool(pending_text)
            pending_text += (" " if pending_text else "") + text
            pending_segments.append({
                "start": start, "end": len(pending_text), "page": page["page"],
                "block": block_number, "ocr": page["method"] == "ocr",
            })
    flush()
    return records


def choose_examples(word, candidates, records, limit=2):
    chosen = []
    seen = set()
    ordered = sorted(candidates, key=lambda i: (records[i]["score"], records[i]["paper_number"], records[i]["id"]))
    for prefer_different in (True, False):
        for index in ordered:
            record = records[index]
            identity = record["text"].lower()
            if identity in seen:
                continue
            if prefer_different and record["paper_number"] in {r["paper_number"] for r in chosen}:
                continue
            if word not in set(tokens(record["text"])):
                raise AssertionError(f"Example does not contain {word}")
            chosen.append(record)
            seen.add(identity)
            if len(chosen) == limit:
                return chosen
    return chosen


def relative_link(target, parent, fragment=""):
    return quote(os.path.relpath(target, parent), safe="/._-") + fragment


def write_outputs(output, extracted, records, counts, document_counts, top, per_book):
    output.mkdir(parents=True, exist_ok=True)
    translation_path = ROOT / "translation_jobs" / "translations.json"
    translations = json.loads(translation_path.read_text()) if translation_path.exists() else {
        "words": {}, "sentences": {},
    }
    books_dir = output / "notebooks"
    books_dir.mkdir(exist_ok=True)
    lookup = defaultdict(list)
    selected_words = {word for word, _ in top}
    for index, record in enumerate(records):
        for word in set(tokens(record["text"])) & selected_words:
            lookup[word].append(index)
    missing = selected_words - set(lookup)
    # Bibliography abbreviations and figure labels may have no full sentence.
    # Preserve their exact rank, and label their original context honestly.
    if missing:
        for item in extracted:
            paper = item["paper"]
            for page in item["pages"]:
                for number, block in enumerate(page["blocks"], 1):
                    matching = set(tokens(block["text"])) & missing
                    if not matching:
                        continue
                    record = {
                        "id": f"P{paper['number']:02d}-P{page['page']:03d}-B{number:03d}",
                        "paper_number": paper["number"], "paper_key": paper["key"],
                        "paper_title": paper["title"], "pdf_path": paper["path"],
                        "pages": [page["page"]],
                        "blocks": [{"page": page["page"], "block": number}],
                        "ocr": page["method"] == "ocr", "text": block["text"],
                        "score": abs(len(block["text"]) - 140), "kind": "original_fragment",
                    }
                    index = len(records)
                    records.append(record)
                    for word in matching:
                        lookup[word].append(index)
    entries = []
    for rank, (word, frequency) in enumerate(top, 1):
        examples = choose_examples(word, lookup[word], records)
        if not examples:
            raise RuntimeError(
                f"No readable full sentence for rank {rank}: {word!r}. "
                "Inspect extraction rather than silently changing the ranking."
            )
        entries.append({
            "rank": rank, "word": word, "frequency": frequency,
            "paper_count": document_counts[word], "examples": examples,
            "word_zh": translations["words"].get(f"w{rank:04d}", ""),
        })
        for example in entries[-1]["examples"]:
            example["translation_zh"] = translations["sentences"].get(example["id"], "")
    for offset in range(0, len(entries), per_book):
        batch = entries[offset:offset + per_book]
        number = offset // per_book + 1
        path = books_dir / f"{number:02d}_{batch[0]['rank']:04d}-{batch[-1]['rank']:04d}.md"
        lines = [
            f"# AI English Vocabulary {number:02d}", "",
            f"Ranks {batch[0]['rank']}-{batch[-1]['rank']} | {len(batch)} words | Frequency: high to low",
            "", "[Index](../README.md)", "",
        ]
        for entry in batch:
            lines += [
                f"## {entry['rank']:04d}. {entry['word']}", "",
            ]
            if entry["word_zh"]:
                lines += [f"**中文：** {entry['word_zh']}", ""]
            lines += [
                f"Occurrences: **{entry['frequency']:,}** | Papers: **{entry['paper_count']}**", "",
            ]
            for index, example in enumerate(entry["examples"], 1):
                # Keep sentence text unaltered: no invented definitions or paraphrases.
                lines += [f"> {example['text']}", ""]
                if example.get("translation_zh"):
                    lines += [f"> **中文：** {example['translation_zh']}", ""]
                if example.get("kind") == "original_fragment":
                    lines += ["Context: **original fragment, not a complete sentence**", ""]
                links = []
                for page in example["pages"]:
                    link = relative_link(ROOT / example["pdf_path"], books_dir, f"#page={page}")
                    links.append(f"[PDF p. {page}]({link})")
                text_link = f"../corpus/{example['paper_number']:02d}_{example['paper_key']}.txt"
                ocr_note = " | OCR, check against the page image" if example["ocr"] else ""
                block_label = ", ".join(f"p.{b['page']}/block {b['block']}" for b in example["blocks"])
                lines += [
                    f"Source {index}: **{example['paper_key']}** | " + ", ".join(links),
                    f"Sentence ID: `{example['id']}` | [extracted text]({text_link}) | {block_label}{ocr_note}",
                    "",
                ]
        path.write_text("\n".join(lines), encoding="utf-8")
    corpus_dir = output / "corpus"
    corpus_dir.mkdir(exist_ok=True)
    for item in extracted:
        paper = item["paper"]
        lines = [paper["title"], f"PDF: {paper['path']}", ""]
        for page in item["pages"]:
            lines += [f"===== PDF PAGE {page['page']} | {page['method']} =====", ""]
            for number, block in enumerate(page["blocks"], 1):
                lines += [f"[BLOCK {number}]", block["text"], ""]
        lines += ["===== INDEXED SENTENCES =====", ""]
        lines += [f"[{r['id']}] PDF pages {r['pages']}\n{r['text']}\n"
                  for r in records if r["paper_number"] == paper["number"]]
        (corpus_dir / f"{paper['number']:02d}_{paper['key']}.txt").write_text("\n".join(lines), encoding="utf-8")
    (output / "vocabulary.json").write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (output / "frequencies.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["rank", "word", "frequency", "paper_count", "selected"])
        for rank, (word, frequency) in enumerate(sorted(counts.items(), key=lambda p: (-p[1], p[0])), 1):
            writer.writerow([rank, word, frequency, document_counts[word], rank <= len(top)])
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "extractor_version": EXTRACTOR_VERSION,
        "paper_count": len(extracted), "page_count": sum(len(p["pages"]) for p in extracted),
        "ocr_pages": [
            {"paper": p["paper"]["key"], "page": page["page"]}
            for p in extracted for page in p["pages"] if page["method"] == "ocr"
        ],
        "total_tokens": sum(counts.values()), "unique_tokens": len(counts),
        "selected_words": len(entries), "notebooks": (len(entries) + per_book - 1) // per_book,
        "examples": sum(len(e["examples"]) for e in entries),
        "single_example_words": [e["word"] for e in entries if len(e["examples"]) == 1],
        "fragment_only_words": [
            e["word"] for e in entries
            if all(r.get("kind") == "original_fragment" for r in e["examples"])
        ],
        "sentence_count": len(records),
        "sources": [{"key": p["paper"]["key"], "sha256": p["sha256"], "path": p["paper"]["path"]} for p in extracted],
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    readme = [
        "# AI English Vocabulary", "",
        f"{len(entries):,} words from {len(extracted)} papers, divided into {report['notebooks']} notebooks.",
        f"{report['total_tokens']:,} counted occurrences; {report['unique_tokens']:,} distinct word forms; "
        f"{report['examples']:,} indexed source sentences.", "",
        "[Open the dark-mode paginated reader](reader.html). Search English, Chinese glosses, and examples.",
        "## Counting Rules", "",
        "- All papers, including appendices, references, and extractable figure/table text, participate.",
        "- No stopword filtering: conjunctions, articles, prepositions, and pronouns are retained.",
        "- Case-insensitive word forms; model and models remain separate. No stemming or lemmatization.",
        "- English alphabetic words and contractions; possessive 's is removed.",
        "- Hyphenated terms are split into words; likely line-wrap hyphenation and ligatures are normalized.",
        "- URLs, emails, bare page numbers, vertical arXiv stamps, and repeated marginal headers/footers are excluded.",
        "- Single letters other than a/i are excluded to avoid counting equation variables as English words.",
        "- Ranking: total occurrence count descending, alphabetical order for ties. No weighting by paper.",
        "", "## Examples and Sources", "",
        "- Each word has up to two distinct full sentences; different papers are preferred when available.",
        "- Exception: words found only in labels/bibliography have explicitly marked original fragments, never invented sentences.",
        "- Quotes reproduce extracted text after whitespace/ligature/line-wrap normalization, not generated sentences.",
        "- PDF page links use 1-based physical PDF pages, not the printed page numbers.",
        "- Search the sentence ID in the linked corpus text to locate the exact sentence and page/block.",
        "- Browser/PDF viewers differ in support for #page links; explicit page labels remain available.",
        f"- OCR was used on {len(report['ocr_pages'])} pages; OCR examples are marked and may contain recognition errors.",
        "- PDF reading order, formulas, reference lists, and OCR remain imperfect; counts describe the documented extracted corpus.",
        "- Each selected word and indexed source excerpt includes a Chinese translation alongside the original English.",
        "", "## Notebooks", "",
        "| Notebook | Ranks | First word | Last word |", "|---|---|---|---|",
    ]
    for offset in range(0, len(entries), per_book):
        batch = entries[offset:offset + per_book]
        number = offset // per_book + 1
        filename = f"{number:02d}_{batch[0]['rank']:04d}-{batch[-1]['rank']:04d}.md"
        readme.append(f"| [{number:02d}](notebooks/{filename}) | {batch[0]['rank']}-{batch[-1]['rank']} | {batch[0]['word']} | {batch[-1]['word']} |")
    readme += [
        "", "## Rebuild", "", "Run from auto_learn with the project virtual environment active:", "", "```bash",
        "python build_vocabulary.py",
        "python translation_pipeline.py merge",
        "python translation_pipeline.py apply",
        "python build_reader.py", "```", "",
        "Extraction is cached by PDF SHA-256 and extractor version. Use --force to regenerate caches.",
        "Use --words / --per-book / --workers / --output to customize the build.",
        "Install dependencies from requirements-vocabulary.txt. NLTK downloads punkt_tab when required.",
        "For a forced OCR rebuild, install Tesseract with English language data and make it available on PATH.",
        "", "Data: vocabulary.json (selected entries), frequencies.csv (all ranks), report.json (QA/provenance), corpus/ (page text).",
        "reader.html is self-contained and embeds the bilingual entries.", "",
    ]
    (output / "README.md").write_text("\n".join(readme), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--words", type=int, default=2500)
    parser.add_argument("--per-book", type=int, default=50)
    parser.add_argument("--workers", type=int, default=min(6, os.cpu_count() or 1))
    parser.add_argument("--output", type=Path, default=ROOT / "vocabulary")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if min(args.words, args.per_book, args.workers) <= 0:
        parser.error("words, per-book, and workers must be positive")
    nltk.data.path.insert(0, str(ROOT / "nltk_data"))
    try:
        tokenizer = PunktTokenizer("english")
    except LookupError:
        nltk.download("punkt_tab", download_dir=str(ROOT / "nltk_data"), raise_on_error=True)
        tokenizer = PunktTokenizer("english")
    tokenizer._params.abbrev_types.update({"fig", "figs", "eq", "eqs", "sec", "secs", "et", "al", "vs", "e.g", "i.e"})
    papers = json.loads((ROOT / "library.json").read_text())
    cache = args.output / ".cache"
    cache.mkdir(parents=True, exist_ok=True)
    executable = shutil.which("tesseract")
    tessdata = os.environ.get("TESSDATA_PREFIX")
    if not tessdata:
        tessdata = next((str(p) for p in [
            Path("/usr/share/tesseract-ocr/5/tessdata"),
            Path("/usr/share/tessdata"),
        ] if (p / "eng.traineddata").exists()), None)
    jobs = [(p, str(cache), executable, tessdata, args.force) for p in papers]
    extracted = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for item in pool.map(extract_paper, jobs):
            extracted.append(item)
            ocr_count = sum(p["method"] == "ocr" for p in item["pages"])
            print(f"Extracted {len(extracted):02d}/{len(papers)} {item['paper']['key']} "
                  f"({len(item['pages'])} pages, {ocr_count} OCR)", flush=True)
    counts = Counter()
    document_counts = Counter()
    records = []
    for item in extracted:
        words = [word for page in item["pages"] for block in page["blocks"] for word in tokens(block["text"])]
        counts.update(words)
        document_counts.update(set(words))
        records.extend(sentence_records(item, tokenizer))
    top = sorted(counts.items(), key=lambda p: (-p[1], p[0]))[:args.words]
    if len(top) != args.words:
        raise RuntimeError(f"Only {len(top)} distinct tokens found")
    report = write_outputs(args.output, extracted, records, counts, document_counts, top, args.per_book)
    print(f"Complete: {report['notebooks']} notebooks, {report['selected_words']} words, "
          f"{report['examples']} source sentences. Output: {args.output}", flush=True)


if __name__ == "__main__":
    main()
