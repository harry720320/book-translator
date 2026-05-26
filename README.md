# Book Translator

A Claude Code skill for translating entire English books into fluent, literary Simplified Chinese (简体中文). Outputs a complete EPUB with cover image, non-spoiler summary, and glossary.

## Features

- **Three format support** — TXT (direct read), EPUB (TOC-aware extraction), PDF (pymupdf extraction)
- **EPUB output** — complete ebook with bilingual title, cover image, summary, chapters, and glossary
- **Simplified Chinese only** — built-in trad→simp character table, enforced before every chapter save
- **Sequential translation** — one chapter at a time with running summary + glossary for cross-chapter consistency
- **Fully autonomous** — runs extraction, translation, cover search, and EPUB build without asking
- **Cover image** — web search by title (DuckDuckGo, Open Library), falls back to plot-based generation
- **Non-spoiler summary** — back-cover style overview at the front of the EPUB
- **Resumable** — state files (`summary.json`, `glossary.json`) allow pausing and resuming mid-book
- **Only 3 Python commands** in the entire translation — extraction, cover fetch, EPUB build. All state updates use native tools (zero Bash prompts during translation loop)

## Installation

```bash
npx skills add https://github.com/harry720320/book-translator --skill book-translator -g -y
```

Or manually: copy this directory to `~/.claude/skills/book-translator/`.

## Usage

Once installed, restart Claude Code. Then:

```
翻译这本书: /path/to/book.epub
```

Or:

```
Translate this EPUB to Chinese: /path/to/book.pdf
```

The skill triggers on: "translate this book", "translate to Chinese", "翻译这本书", "英译中", "book translation", "translate this novel", "can you translate", "帮我翻译", "把这本书翻成中文", "简体中文版", or whenever a book file is provided in a translation context.

## How it works

### Phase 1: Extract & Setup

The skill auto-detects the input format and runs the appropriate extraction script:

| Format | Script | Method |
|--------|--------|--------|
| TXT | direct read | Chapter markers or ~2500-word splits |
| EPUB | `scripts/extract_epub.py` | TOC/spine parsing, HTML fallback |
| PDF | `scripts/extract_pdf.py` | pymupdf text extraction, heading detection |

It then searches for a cover image via `scripts/fetch_cover.py` — searches the web first, generates a themed cover from plot text as fallback.

### Phase 2: Translate (sequential, no parallel agents)

Each chapter is translated with context from two state files:

- **`summary.json`** — running plot summary, current situation, pending threads
- **`glossary.json`** — character names, places, and terms with English→Chinese mappings

Translation follows literary Simplified Chinese guidelines:
- Simplified Chinese only — traditional characters are detected and replaced before saving
- Natural sentence rhythm (break long English sentences, vary length)
- Idiomatic handling of metaphors and cultural references
- Avoidance of translationese markers (excessive 的, 被-passive, 当...的时候)

No parallel agents — each chapter reads the running summary before translating, ensuring terminology and plot consistency.

### Phase 3: Non-Spoiler Summary

A 150-300 character Chinese summary is generated from the running summary, written in back-cover style — revealing only what a dust jacket would, without spoiling major plot twists or the ending.

### Phase 4: Build EPUB

`scripts/build_epub.py` produces `workspace/<ChineseTitle>.epub` with proper NCX/NAV navigation:

1. **Cover page** — cover image
2. **Title page** — bilingual title ("English Title —— 中文书名") + author + translator credit
3. **内容简介** — non-spoiler Chinese summary
4. **Chapters** — each translated chapter as a separate section with proper paragraph breaks
5. **翻译术语表** — complete glossary appendix

### EPUB metadata

- **Title**: bilingual (English + Chinese)
- **Author**: original author
- **Translator**: Claude (AI Literary Translator)
- **Language**: zh-CN

### Workspace structure

```
workspace/
├── extracted/
│   ├── metadata.json
│   └── chapters/
│       ├── chapter_0001.txt
│       └── ...
├── translated/
│   ├── chapter_0001.md
│   └── ...
├── cover.jpg
├── summary.json
├── glossary.json
├── summary_cn.txt
└── <ChineseTitle>.epub        ← final deliverable
```

## Dependencies

```bash
pip install ebooklib beautifulsoup4 lxml pymupdf Pillow requests
```

## Edge case handling

- **PDF misdetection**: pages wrongly identified as chapters → auto-merge and re-split
- **DRM-protected EPUB**: detected and reported, translation stops
- **Scanned PDFs** (no text layer): detected and reported
- **Resume after interruption**: state files track progress, next session continues from `last_chapter + 1`
- **Very large books** (>100K words): translate as far as possible, resume in new session

## Optimization

This skill was optimized using the [Darwin Skill](https://github.com/alchaincyf/darwin-skill) framework (8-dimension rubric):

| Metric | Before | After |
|--------|--------|-------|
| Darwin Score | 73.3 | 77.6 (+5.9%) |
| Rounds | — | 4/4 kept, 0 reverts |
| Key improvements | — | Resource integration, boundary conditions, frontmatter, TL;DR card |

## License

MIT
