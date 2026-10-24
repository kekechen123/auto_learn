#!/usr/bin/env python3
"""Prepare isolated translation batches, merge agent JSON, and apply translations."""

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "vocabulary"
JOBS = ROOT / "translation_jobs"
WORDS_PER_BATCH = 100
SENTENCES_PER_BATCH = 80
CJK_RE = re.compile(r"[\u3400-\u9fff]")


def load_targets():
    entries = json.loads((OUT / "vocabulary.json").read_text())
    words = [
        {"id": f"w{entry['rank']:04d}", "text": entry["word"]}
        for entry in entries
    ]
    sentences = {}
    for entry in entries:
        for example in entry["examples"]:
            sentences[example["id"]] = example["text"]
    return entries, words, [{"id": key, "text": text} for key, text in sentences.items()]


def prepare():
    _, words, sentences = load_targets()
    input_dir = JOBS / "inputs"
    result_dir = JOBS / "results"
    input_dir.mkdir(parents=True, exist_ok=True)
    result_dir.mkdir(parents=True, exist_ok=True)
    batch_count = max(
        (len(words) + WORDS_PER_BATCH - 1) // WORDS_PER_BATCH,
        (len(sentences) + SENTENCES_PER_BATCH - 1) // SENTENCES_PER_BATCH,
    )
    for number in range(batch_count):
        payload = {
            "batch": number + 1,
            "words": words[number * WORDS_PER_BATCH:(number + 1) * WORDS_PER_BATCH],
            "sentences": sentences[number * SENTENCES_PER_BATCH:(number + 1) * SENTENCES_PER_BATCH],
        }
        path = input_dir / f"{number + 1:02d}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    manifest = {
        "batch_count": batch_count, "word_count": len(words),
        "sentence_count": len(sentences), "words_per_batch": WORDS_PER_BATCH,
        "sentences_per_batch": SENTENCES_PER_BATCH,
    }
    (JOBS / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


def merge():
    _, words, sentences = load_targets()
    expected_words = {item["id"] for item in words}
    expected_sentences = {item["id"] for item in sentences}
    word_overrides = {
        "w0511": "线；研究方向",
        "w0526": "姓氏（Le）",
        "w0575": "平均值；意味着",
        "w0579": "任一；或者",
        "w0583": "在……中；英语缩写（En.）",
        "w0041": "Gemini（双子座；谷歌模型名）",
        "w0049": "GPT（生成式预训练 Transformer）",
        "w0163": "Llama（羊驼；模型名）",
        "w0194": "DeepSeek（深度求索；模型名）",
        "w0227": "ImageNet（图像识别数据集）",
        "w0235": "x_t（时刻 t 的变量）",
        "w0286": "CLIP（图文对比预训练模型）",
        "w0465": "OpenAI（人工智能研究机构）",
        "w1114": "GitHub（代码托管平台）",
        "w1315": "LeNet（卷积神经网络）",
        "w1398": "PMS（缩写，保留原文）",
        "w1416": "PMLR（机器学习研究论文集）",
        "w1439": "DDIM（去噪扩散隐式模型）",
        "w1972": "PDF（便携式文档格式）",
        "w1983": "ACM（计算机协会）",
    }
    sentence_prefixes = {
        "P48-S00383": "作者名单：",
        "P47-S00359": "作者名单：",
        "P20-S00296": "作者名单：",
        "P42-S00205": "作者名单：",
        "P48-S00380": "作者名单：",
        "P20-S00305": "作者名单：",
    }
    merged_words = {}
    merged_sentences = {}
    for batch_file in sorted((JOBS / "inputs").glob("*.json")):
        result_file = JOBS / "results" / batch_file.name
        if not result_file.exists():
            raise FileNotFoundError(f"Missing result: {result_file}")
        task = json.loads(batch_file.read_text())
        result = json.loads(result_file.read_text())
        if set(result) != {"words", "sentences"}:
            raise ValueError(f"{result_file}: expected only words and sentences")
        expected_batch_words = {item["id"] for item in task["words"]}
        expected_batch_sentences = {item["id"] for item in task["sentences"]}
        if set(result["words"]) != expected_batch_words:
            raise ValueError(f"{result_file}: word IDs do not match input")
        if set(result["sentences"]) != expected_batch_sentences:
            raise ValueError(f"{result_file}: sentence IDs do not match input")
        for key, translation in result["words"].items():
            if not isinstance(translation, str) or not translation.strip():
                raise ValueError(f"{result_file}: empty/non-text word translation {key}")
            translation = word_overrides.get(key, translation.strip())
            if not CJK_RE.search(translation):
                raise ValueError(f"{result_file}: word translation lacks Chinese characters: {key}")
            if key in merged_words:
                raise ValueError(f"Duplicate word translation: {key}")
            merged_words[key] = translation
        for key, translation in result["sentences"].items():
            if not isinstance(translation, str) or not translation.strip():
                raise ValueError(f"{result_file}: empty/non-text sentence translation {key}")
            translation = sentence_prefixes.get(key, "") + translation.strip()
            if not CJK_RE.search(translation):
                raise ValueError(f"{result_file}: sentence translation lacks Chinese characters: {key}")
            if key in merged_sentences:
                raise ValueError(f"Duplicate sentence translation: {key}")
            merged_sentences[key] = translation
    if set(merged_words) != expected_words:
        raise ValueError(f"Word coverage mismatch: missing={len(expected_words-set(merged_words))}")
    if set(merged_sentences) != expected_sentences:
        raise ValueError(f"Sentence coverage mismatch: missing={len(expected_sentences-set(merged_sentences))}")
    payload = {"words": merged_words, "sentences": merged_sentences}
    path = JOBS / "translations.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Merged {len(merged_words)} word glosses and {len(merged_sentences)} unique sentence translations.")


def apply():
    translations = json.loads((JOBS / "translations.json").read_text())
    entries, _, _ = load_targets()
    for entry in entries:
        entry["word_zh"] = translations["words"][f"w{entry['rank']:04d}"]
        for example in entry["examples"]:
            example["translation_zh"] = translations["sentences"][example["id"]]
    (OUT / "vocabulary.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    word_heading = re.compile(r"^## (\d{4})\. (.+)$")
    sentence_marker = re.compile(r"^Sentence ID: `?([^` |]+)`?.*$")
    for notebook in sorted((OUT / "notebooks").glob("*.md")):
        lines = notebook.read_text(encoding="utf-8").splitlines()
        updated = []
        index = 0
        while index < len(lines):
            line = lines[index]
            word_match = word_heading.match(line)
            sentence_match = sentence_marker.match(line)
            translation_line = None
            if word_match:
                rank = int(word_match.group(1))
                translation_line = f"**中文：** {translations['words'][f'w{rank:04d}']}"
            elif sentence_match:
                translated = translations["sentences"].get(sentence_match.group(1))
                if translated:
                    translation_line = f"> **中文：** {translated}"

            updated.append(line)
            if translation_line is not None:
                existing_prefix = "> **中文：** " if sentence_match else "**中文：** "
                if index + 1 < len(lines) and lines[index + 1].startswith(existing_prefix):
                    index += 1
                    updated.append(translation_line)
                else:
                    updated.append(translation_line)
            index += 1
        notebook.write_text("\n".join(updated) + "\n", encoding="utf-8")
    readme = OUT / "README.md"
    readme_text = readme.read_text()
    if "## Chinese Translations" not in readme_text:
        readme_text += (
            "\n## Chinese Translations\n\n"
            f"- Added Chinese glosses for {len(entries):,} words.\n"
            f"- Added Chinese translations for {len(translations['sentences']):,} unique source excerpts.\n"
            "- Translation batches and their provenance are in ../translation_jobs/.\n"
        )
        readme.write_text(readme_text, encoding="utf-8")
    print(f"Applied Chinese to {len(entries)} words and {len(translations['sentences'])} unique sentences.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "merge", "apply"))
    args = parser.parse_args()
    {"prepare": prepare, "merge": merge, "apply": apply}[args.command]()


if __name__ == "__main__":
    main()
