# Book Translator

A Claude Code skill for translating entire English books into fluent, literary Simplified Chinese (简体中文). Outputs a complete EPUB with cover image, non-spoiler summary, and glossary.

## Features

- **Three format support** — TXT (direct read), EPUB (TOC-aware extraction), PDF (pymupdf extraction)
- **EPUB output** — complete ebook with bilingual title, cover image, summary, chapters, and glossary
- **Enhanced literary translation** — rewritten style guide with before/after examples, prioritized checklist, register-specific patterns, and sentence-splitting decision tree
- **Per-chapter review agent** — parallel background agent runs structured quality review (4-dimension rubric + deterministic checks) on each chapter as translation continues
- **Deterministic quality checks** — zero-model-cost script scans for traditional characters, 的 density, 被-passive, 当...的时候, 和 overuse, sentence variance, and glossary drift
- **Simplified Chinese only** — built-in trad→simp character table, scanned before every chapter save
- **Sequential translation** — one chapter at a time with running summary + glossary for cross-chapter consistency
- **Fully autonomous** — runs extraction, translation, review, cover search, and EPUB build without asking
- **Cover image** — web search by title and author, falls back to plot-based generation
- **Non-spoiler summary** — back-cover style overview at the front of the EPUB
- **Resumable** — state files (`summary.json`, `glossary.json`) allow pausing and resuming mid-book
- **Only 3 Python commands** in the entire translation — extraction, cover fetch, EPUB build. All state updates use native tools (zero Bash prompts during translation loop)

## Quality System

The skill includes a full quality improvement pipeline:

### Runtime Review

During translation, each chapter undergoes automated review by a parallel agent:
- **Deterministic checks** (`scripts/quality_check.py`) — traditional characters, 的 density, 被-passive, glossary drift, sentence variance
- **Structured rubric** (`references/review-prompt.md`) — 4-dimension scoring: naturalness, register match, dialogue quality, translationese
- The review agent edits chapters directly and runs in the background while the next chapter translates

### Three-Layer Evaluation

| Layer | Script | What it measures |
|---|---|---|
| 1 — Automated Metrics | `scripts/eval_metrics.py` | Aggregated quality checks across all chapters, zero model cost |
| 2 — Model-as-Judge | `scripts/eval_rubric.py` | 5-dimension rubric scoring (naturalness, register, dialogue, literary quality, terminology) |
| 3 — Blind A/B | `scripts/eval_ab.py` | Position-swapped blind comparison between prompt versions |

### Prompt Tuning

`scripts/tune_prompt.py` orchestrates a fully automated tuning loop:
1. Translate test corpus with current prompt
2. Run all 3 evaluation layers
3. Prompt doctor diagnoses gaps and proposes edits
4. Apply edits, re-evaluate, keep if all layers improve, revert otherwise
5. Repeat until convergence

Converged at v1: L2 rubric average improved from 4.4 → 4.6, description sample from needs_review (4.2) → clean (5.0).

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

### Phase 2: Translate with Review

Each chapter is translated with context from two state files:

- **`summary.json`** — running plot summary, current situation, pending threads
- **`glossary.json`** — character names, places, and terms with English→Chinese mappings

Translation follows the enhanced literary Simplified Chinese guidelines in `references/translation-style.md`:
- **Prioritized checklist**: break modifier chains → convert 被-passive → drop pronouns → replace 当...的时候 → vary sentence length → reduce 的 density
- **Register-specific patterns**: dialogue (6-15 chars, particles), narration (varied rhythm), action (8-20 chars, strong verbs), description (20-40 chars, sensory details)
- **Sentence splitting decision tree**: split by clause count, modifier chains, register, and mixed content
- **Before/after examples** for every anti-pattern

After each chapter is saved, a **review agent** is spawned in the background:
1. Runs `quality_check.py` for deterministic issues
2. Scores the chapter on the 4-dimension review rubric
3. Edits the chapter file directly to fix clear issues
4. Updates glossary.json if terminology was corrected
5. Writes review summary to `workspace/reviews/`

The review runs in parallel — the main agent continues to the next chapter immediately.

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
├── reviews/
│   ├── chapter_0001_review.json
│   └── ...
├── cover.jpg
├── summary.json
├── glossary.json
├── summary_cn.txt
└── <ChineseTitle>.epub        ← final deliverable
```

## Offline Tools

### Quality Check

```bash
# Single chapter
python scripts/quality_check.py workspace/translated/chapter_0001.md --glossary workspace/glossary.json

# All chapters (Layer 1 eval)
python scripts/eval_metrics.py workspace/translated/ --glossary workspace/glossary.json
```

### Model-as-Judge Evaluation

```bash
# Prepare evaluation batch
python scripts/eval_rubric.py workspace/translated/ workspace/extracted/chapters/ --prepare-only

# Aggregate scores after agent evaluation
python scripts/eval_rubric.py --aggregate workspace/eval_results/
```

### Blind A/B Comparison

```bash
python scripts/eval_ab.py source.txt translation_v1.md translation_v2.md --runs 3 --label-a v1 --label-b v2
```

### Prompt Tuning

```bash
# Start tuning loop
python scripts/tune_prompt.py . --max-iterations 5

# Apply iteration results
python scripts/tune_prompt.py . --apply eval-results/iter_1

# Generate report
python scripts/tune_prompt.py . --report
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
- **Review alerts**: structural/plot inconsistencies flagged by review agent → addressed before EPUB build

## Tuning History

| Iteration | Kept | Key Change | Impact |
|---|---|---|---|
| 1 | Yes | Added literary 被-passive + 的-density examples | Description L2: 4.2 → 5.0 |
| 2 | No | Character voice differentiation | Reverted — net zero (naturalness +1, dialogue -1) |

Converged at v1 with L2 average 4.6 across test corpus.

## License

MIT
