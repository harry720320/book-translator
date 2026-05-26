# Book Translator

A Claude Code skill for translating entire English books into fluent, literary Chinese. Supports TXT, EPUB, and PDF input formats.

## Features

- **Three format support** — TXT (direct read), EPUB (TOC-aware extraction), PDF (pymupdf extraction)
- **Chapter-by-chapter translation** — maintains a running summary and glossary for cross-chapter consistency
- **Resumable** — state files (`summary.json`, `glossary.json`) allow pausing and resuming mid-book
- **Literary quality** — follows anti-translationese guidelines: natural Chinese rhythm, idiomatic handling of metaphors, consistent name transliteration
- **Single output** — final `output.md` with all chapters plus a glossary appendix

## Installation

```bash
npx skills add https://github.com/hwang2/book-translator --skill book-translator -g -y
```

Or manually: copy this directory to `~/.claude/skills/book-translator/`.

## Usage

Once installed, restart Claude Code. Then:

```
Translate this EPUB to Chinese: /path/to/book.epub
```

Or:

```
把这本书翻译成中文: /path/to/book.txt
```

The skill triggers on: "translate this book", "translate to Chinese", "翻译这本书", "英译中", "book translation", or when you provide a book file and ask for Chinese translation.

## How it works

### Phase 1: Extract

The skill auto-detects the input format and runs the appropriate extraction script:

| Format | Script | Method |
|--------|--------|--------|
| TXT | direct read | Chapter markers or ~3000-word splits |
| EPUB | `scripts/extract_epub.py` | TOC/spine parsing, HTML fallback |
| PDF | `scripts/extract_pdf.py` | pymupdf text extraction, heading detection |

Extracted chapters are saved to `workspace/extracted/chapters/` and the user confirms chapter boundaries before proceeding.

### Phase 2: Translate

Each chapter is translated independently with context from two state files:

- **`summary.json`** — running plot summary, current situation, pending threads
- **`glossary.json`** — character names, places, and terms with English→Chinese mappings

The translation follows literary Chinese guidelines:
- Natural sentence rhythm (break long English sentences, vary length)
- Idiomatic handling of metaphors and cultural references
- Avoidance of translationese markers (excessive 的, 被-passive, 当...的时候)
- Consistent name transliteration across all chapters

### Phase 3: Assemble

All translated chapters are combined into a single `output.md` with a glossary appendix listing every character, place, and term translated.

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
├── summary.json
├── glossary.json
└── output.md
```

## Dependencies

```bash
pip install ebooklib beautifulsoup4 lxml pymupdf
```

## Evaluation

This skill was evaluated against a baseline (Claude's default translation) on 3 test cases:

| Metric | With Skill | Without Skill |
|--------|-----------|---------------|
| Pass Rate | 100% | 94% |
| Glossary | Yes | No |
| Translationese | Zero 被-passive | 1 borderline trigger |

The skill wraps [anthropics/skill-creator](https://github.com/anthropics/skills) evaluation workflow.

## License

MIT
