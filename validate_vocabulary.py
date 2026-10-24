#!/usr/bin/env python3
"""Independently validate notebook sizes, ranks, citations, and local links."""

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

from build_vocabulary import ROOT, tokens


def validate(output):
    entries = json.loads((output / "vocabulary.json").read_text())
    report = json.loads((output / "report.json").read_text())
    books = sorted((output / "notebooks").glob("*.md"))
    assert len(books) == report["notebooks"], "Unexpected notebook count"
    assert len(entries) == report["selected_words"], "Unexpected word count"
    assert len({e["word"] for e in entries}) == len(entries), "Duplicate vocabulary"
    ranks = []
    for book in books:
        text = book.read_text()
        headings = re.findall(r"^## (\d+)\. (.+)$", text, re.M)
        if report["selected_words"] == 2500 and report["notebooks"] == 50:
            assert len(headings) == 50, f"{book}: expected 50 entries"
        ranks.extend(int(rank) for rank, _ in headings)
        for target in re.findall(r"\]\(([^)]+)\)", text):
            assert (book.parent / unquote(target.split("#")[0])).exists(), f"Broken link: {target}"
    assert ranks == list(range(1, len(entries) + 1)), "Missing or unordered ranks"
    counts = Counter()
    document_counts = Counter()
    cache = {}
    for path in (output / ".cache").glob("*.json"):
        item = json.loads(path.read_text())
        cache[item["paper"]["number"]] = item
    assert len(cache) == report["paper_count"]
    corpus_text = {}
    for source in report["sources"]:
        item = next(p for p in cache.values() if p["paper"]["key"] == source["key"])
        assert item["sha256"] == source["sha256"]
        words = [
            word for page in item["pages"] for block in page["blocks"]
            for word in tokens(block["text"])
        ]
        counts.update(words)
        document_counts.update(set(words))
        paper = item["paper"]
        corpus_text[paper["number"]] = (
            output / "corpus" / f"{paper['number']:02d}_{paper['key']}.txt"
        ).read_text()
    expected = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:len(entries)]
    assert [(e["word"], e["frequency"]) for e in entries] == expected, "Ranking mismatch"
    citation_count = 0
    for entry in entries:
        assert entry["paper_count"] == document_counts[entry["word"]]
        assert 1 <= len(entry["examples"]) <= 2
        assert len({s["text"].lower() for s in entry["examples"]}) == len(entry["examples"])
        for sentence in entry["examples"]:
            assert entry["word"] in set(tokens(sentence["text"])), (entry["word"], sentence["id"])
            item = cache[sentence["paper_number"]]
            joined = " ".join(
                item["pages"][block["page"] - 1]["blocks"][block["block"] - 1]["text"]
                for block in sentence["blocks"]
            )
            assert sentence["text"] in joined, f"Untraceable quote: {sentence['id']}"
            assert f"[{sentence['id']}]" in corpus_text[sentence["paper_number"]]
            citation_count += 1
    assert citation_count == report["examples"]
    print(f"PASS: {len(books)} notebooks, {len(entries)} unique ranked words, "
          f"{citation_count} traceable citations; all links resolve.")
    print(f"Single-example words: {report['single_example_words']}")
    print(f"Original-fragment exceptions: {report['fragment_only_words']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "vocabulary")
    validate(parser.parse_args().output)
