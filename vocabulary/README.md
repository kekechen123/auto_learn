# AI English Vocabulary

2,500 words from 50 papers, divided into 50 notebooks.
873,490 counted occurrences; 32,849 distinct word forms; 4,998 indexed source sentences.

[Open the dark-mode paginated reader](reader.html). It shows 50 words per page and supports English/Chinese search.

## Counting Rules

- All papers, including appendices, references, and extractable figure/table text, participate.
- No stopword filtering: conjunctions, articles, prepositions, and pronouns are retained.
- Case-insensitive word forms; model and models remain separate. No stemming or lemmatization.
- English alphabetic words and contractions; possessive 's is removed.
- Hyphenated terms are split into words; likely line-wrap hyphenation and ligatures are normalized.
- URLs, emails, bare page numbers, vertical arXiv stamps, and repeated marginal headers/footers are excluded.
- Single letters other than a/i are excluded to avoid counting equation variables as English words.
- Ranking: total occurrence count descending, alphabetical order for ties. No weighting by paper.

## Examples and Sources

- Each word has up to two distinct full sentences; different papers are preferred when available.
- Exception: words found only in labels/bibliography have explicitly marked original fragments, never invented sentences.
- Quotes reproduce extracted text after whitespace/ligature/line-wrap normalization, not generated sentences.
- PDF page links use 1-based physical PDF pages, not the printed page numbers.
- Search the sentence ID in the linked corpus text to locate the exact sentence and page/block.
- Browser/PDF viewers differ in support for #page links; explicit page labels remain available.
- OCR was used on 50 pages; OCR examples are marked and may contain recognition errors.
- PDF reading order, formulas, reference lists, and OCR remain imperfect; counts describe the documented extracted corpus.
- Each selected word and indexed source excerpt includes a Chinese translation alongside the original English.

## Notebooks

| Notebook | Ranks | First word | Last word |
|---|---|---|---|
| [01](notebooks/01_0001-0050.md) | 1-50 | the | have |
| [02](notebooks/02_0051-0100.md) | 51-100 | shot | information |
| [03](notebooks/03_0101-0150.md) | 101-150 | section | transformer |
| [04](notebooks/04_0151-0200.md) | 151-200 | given | benchmarks |
| [05](notebooks/05_0201-0250.md) | 201-250 | similar | sequence |
| [06](notebooks/06_0251-0300.md) | 251-300 | inference | right |
| [07](notebooks/07_0301-0350.md) | 301-350 | knowledge | standard |
| [08](notebooks/08_0351-0400.md) | 351-400 | post | smaller |
| [09](notebooks/09_0401-0450.md) | 401-450 | lower | box |
| [10](notebooks/10_0451-0500.md) | 451-500 | control | common |
| [11](notebooks/11_0501-0550.md) | 501-550 | free | early |
| [12](notebooks/12_0551-0600.md) | 551-600 | pattern | main |
| [13](notebooks/13_0601-0650.md) | 601-650 | online | daniel |
| [14](notebooks/14_0651-0700.md) | 651-700 | hate | suppose |
| [15](notebooks/15_0701-0750.md) | 701-750 | users | metrics |
| [16](notebooks/16_0751-0800.md) | 751-800 | now | makes |
| [17](notebooks/17_0801-0850.md) | 801-850 | times | race |
| [18](notebooks/18_0851-0900.md) | 851-900 | swin | dev |
| [19](notebooks/19_0901-0950.md) | 901-950 | respect | mathematics |
| [20](notebooks/20_0951-1000.md) | 951-1000 | turbo | explore |
| [21](notebooks/21_1001-1050.md) | 1001-1050 | labelers | components |
| [22](notebooks/22_1051-1100.md) | 1051-1100 | fit | created |
| [23](notebooks/23_1101-1150.md) | 1101-1150 | crowdworkers | chelsea |
| [24](notebooks/24_1151-1200.md) | 1151-1200 | demonstrated | corresponds |
| [25](notebooks/25_1201-1250.md) | 1201-1250 | discussion | generalize |
| [26](notebooks/26_1251-1300.md) | 1251-1300 | ilsvrc | reason |
| [27](notebooks/27_1301-1350.md) | 1301-1350 | recipe | man |
| [28](notebooks/28_1351-1400.md) | 1351-1400 | middle | robotics |
| [29](notebooks/29_1401-1450.md) | 1401-1450 | row | quoc |
| [30](notebooks/30_1451-1500.md) | 1451-1500 | requiring | french |
| [31](notebooks/31_1501-1550.md) | 1501-1550 | george | threat |
| [32](notebooks/32_1551-1600.md) | 1551-1600 | varying | moe |
| [33](notebooks/33_1601-1650.md) | 1601-1650 | properties | mitigate |
| [34](notebooks/34_1651-1700.md) | 1651-1700 | nicholas | luke |
| [35](notebooks/35_1701-1750.md) | 1701-1750 | minimum | news |
| [36](notebooks/36_1751-1800.md) | 1751-1800 | option | jan |
| [37](notebooks/37_1801-1850.md) | 1801-1850 | metadata | course |
| [38](notebooks/38_1851-1900.md) | 1851-1900 | depending | depends |
| [39](notebooks/39_1901-1950.md) | 1901-1950 | derived | connection |
| [40](notebooks/40_1951-2000.md) | 1951-2000 | crop | iteration |
| [41](notebooks/41_2001-2050.md) | 2001-2050 | labeler | xiong |
| [42](notebooks/42_2051-2100.md) | 2051-2100 | ablations | partial |
| [43](notebooks/43_2101-2150.md) | 2101-2150 | perhaps | zettlemoyer |
| [44](notebooks/44_2151-2200.md) | 2151-2200 | academic | la |
| [45](notebooks/45_2201-2250.md) | 2201-2250 | lambada | story |
| [46](notebooks/46_2251-2300.md) | 2251-2300 | sufficiently | arms |
| [47](notebooks/47_2301-2350.md) | 2301-2350 | bart | kinds |
| [48](notebooks/48_2351-2400.md) | 2351-2400 | outlined | sdnn |
| [49](notebooks/49_2401-2450.md) | 2401-2450 | share | variations |
| [50](notebooks/50_2451-2500.md) | 2451-2500 | aidan | yw |

## Rebuild

Run from auto_learn:

```bash
python3 build_vocabulary.py
python3 translation_pipeline.py merge
python3 translation_pipeline.py apply
python3 build_reader.py
```

Extraction is cached by PDF SHA-256 and extractor version. Use --force to regenerate caches.
Activate the project virtual environment first; use --words / --per-book / --workers / --output to customize the build.
Dependencies: requirements-vocabulary.txt. NLTK downloads punkt_tab when required.
For a forced OCR rebuild, install Tesseract with English language data and make it available on PATH.

Data: vocabulary.json (selected entries), frequencies.csv (all ranks), report.json (QA/provenance), corpus/ (page text).
reader.html is a self-contained bilingual reading interface; rerun build_reader.py after vocabulary translations change.

## Chinese Translations

- Added Chinese glosses for 2,500 words.
- Added Chinese translations for 1,993 unique source excerpts.
- Translation batches and their provenance are in ../translation_jobs/.
