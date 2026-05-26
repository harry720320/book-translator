---
name: book-translator
description: Translate entire English books into fluent, literary Simplified Chinese (简体中文). Supports TXT, EPUB, and PDF input. Outputs a complete EPUB with bilingual title, non-spoiler summary, and cover image. Use when the user wants to translate a book, novel, or long English text into Chinese. Triggers on "translate this book", "translate to Chinese", "翻译这本书", "英译中", "book translation", "translate this novel", "turn this into Chinese", or whenever someone provides a book file (.txt, .epub, .pdf) and asks for Chinese translation. Also use when the user wants to translate long-form English content with consistent terminology.
---

# Book Translator

Translate entire English books into natural, literary **Simplified Chinese (简体中文)** — the kind that reads as if it were originally written in Chinese. Output is a complete EPUB file with cover, summary, and glossary.

## CRITICAL: Execution Rules

These rules override any default behavior. Follow them strictly.

### Rule 1: Simplified Chinese ONLY
Every translated word must be in **Simplified Chinese (简体中文)**. Traditional Chinese characters (繁體字) are forbidden. Before saving each chapter, scan for traditional characters and replace them with simplified equivalents. Common traditional→simplified pairs: 説→说, 時→时, 個→个, 們→们, 來→来, 後→后, 會→会, 過→过, 對→对, 開→开, 關→关, 學→学, 見→见, 裡→里, 麼→么, 寫→写. If you see any character not in the standard simplified set, fix it.

### Rule 2: Sequential translation ONLY — NO parallel agents
Translate chapters one at a time, in order. Never spawn sub-agents to translate multiple chapters in parallel. Each chapter's translation must read `workspace/summary.json` before translating — this is the ONLY way to maintain terminology and plot consistency across chapters. A sub-agent does not have access to the running summary and will produce inconsistent output.

### Rule 3: NO asking for approval
Once the user says "translate this book" (or equivalent), execute EVERY step without pausing:
- Run extraction scripts without asking
- Translate every chapter without asking "should I continue?"
- Build the EPUB without asking
- Search for a cover image without asking
The ONLY time you report progress is after each chapter: "Chapter N/M done." Do not ask. Just do.

### Rule 4: Output as EPUB
The final deliverable is an EPUB file, not Markdown. After translating all chapters, run `scripts/build_epub.py` to assemble the EPUB with proper metadata.

## High-Level Flow

```
Input file (.txt/.epub/.pdf)
    → Extract text + detect chapters (scripts/)
    → Search for cover image (scripts/fetch_cover.py)
    → Translate chapter by chapter WITH running summary context
    → Generate non-spoiler summary
    → Build EPUB (scripts/build_epub.py)
    → Final deliverable: workspace/<BookTitle>.epub
```

## Phase 1: Extraction & Setup

### 1a. Verify dependencies

Before any extraction, ensure required Python packages are installed. Run once:

```bash
pip install ebooklib beautifulsoup4 lxml pymupdf Pillow requests
```

If a script fails with ModuleNotFoundError, install the missing package and retry. Do not ask the user — just install what's needed.

### 1b. Locate scripts

All bundled scripts live in the skill's `scripts/` directory. Resolve paths relative to the skill root:

| Script | Purpose | Command |
|--------|---------|---------|
| `scripts/extract_epub.py` | EPUB → text + chapters | `python <skill_root>/scripts/extract_epub.py` |
| `scripts/extract_pdf.py` | PDF → text + chapters | `python <skill_root>/scripts/extract_pdf.py` |
| `scripts/fetch_cover.py` | Web search or generate cover | `python <skill_root>/scripts/fetch_cover.py` |
| `scripts/build_epub.py` | Assemble final EPUB | `python <skill_root>/scripts/build_epub.py` |

The skill root is typically `~/.claude/skills/book-translator/` (global install) or the directory containing this SKILL.md. If unsure, use the absolute path to the skill directory.

### 1c. Run the extraction script

Detect format and run the appropriate script immediately — do NOT ask for confirmation:

**TXT**: Read directly and split by chapter markers or ~3000-word boundaries.

**EPUB**:
```bash
python scripts/extract_epub.py "<book.epub>" workspace/extracted/
```

**PDF**:
```bash
python scripts/extract_pdf.py "<book.pdf>" workspace/extracted/
```

If the extraction produces too many or too few chapters, fix it silently. For PDFs where every page was misidentified as a chapter: merge all text and re-split at paragraph boundaries into ~2500-word chunks. Adapt to the actual structure of the book.

### 1d. Initialize state files

Create `workspace/glossary.json`:
```json
{"characters": {}, "places": {}, "terms": {}}
```

Create `workspace/summary.json`:
```json
{"last_chapter": 0, "plot_summary": "", "current_situation": "", "pending_threads": []}
```

Create `workspace/translated/` directory.

### 1e. Search for cover image

```bash
python scripts/fetch_cover.py "<Book Title>" "workspace/cover.jpg"
```

This script:
1. Searches the web for the book's cover image by title + author
2. If found: downloads the best match to `workspace/cover.jpg`
3. If not found: generates a thematic cover image based on the extracted text using ASCII/geometric art, saves to `workspace/cover.jpg`
4. Reports: "Cover: [found online / generated from plot]"

## Handling Edge Cases

### Resuming after interruption

If the session ends mid-book, a new session can pick up seamlessly. On startup, check if `workspace/summary.json` exists with `last_chapter` > 0. If so, resume from `last_chapter + 1` — all context is preserved in the state files. Do NOT re-extract or re-translate chapters that are already done.

### Very large books (>100K words)

For books exceeding 100K words, the translation loop may exceed session limits. Strategy:
1. Translate as many chapters as possible in the current session
2. State is auto-saved after every chapter (`summary.json`, `glossary.json`)
3. The user can resume in a new session by re-invoking the skill — it detects existing state and continues
4. If a single chapter exceeds ~5000 words, split it into sub-sections and translate each with the same running context

### EPUB with no TOC or spine

If the EPUB extraction script returns empty results (no TOC, no recognizable spine):
1. Fall back to ZIP+HTML parsing (already built into `extract_epub.py`)
2. If that also fails, extract all text from every HTML file, merge, and split by heading patterns or ~2500-word boundaries
3. If the EPUB is DRM-protected: report "This EPUB appears to be DRM-protected and cannot be extracted" and stop

### PDF with no extractable text (scanned book)

If the PDF extraction returns fewer than 500 total words:
1. Report: "This PDF appears to be a scanned document (image-based, no text layer). OCR is needed."
2. Do NOT attempt OCR — it requires specialized tools beyond this skill's scope

### TXT with no chapter markers

Split the text into ~2500-word chunks at paragraph boundaries. Name them `chapter_0001.txt`, `chapter_0002.txt`, etc. The book will still translate correctly — the running summary maintains cross-chapter continuity regardless of where chapters are split.

## Phase 2: Translation Loop

Read `references/translation-style.md` for the full literary Chinese translation guidelines. Key mandates:

1. **Simplified Chinese ONLY (简体中文)** — scan every chapter for traditional characters before saving
2. Use the glossary for ALL names and terms
3. Natural Chinese rhythm — break long English sentences, vary sentence length
4. No translationese: avoid excessive 的, 被, 当...的时候, 和-everywhere

### The loop — execute all chapters without pausing

For each chapter N from 1 to total:

**Step 1**: Read `workspace/extracted/chapters/chapter_NNNN.txt`

**Step 2**: Read `workspace/summary.json` and `workspace/glossary.json` for context

**Step 3**: Translate into Simplified Chinese. Follow the guidelines in `references/translation-style.md`. Use glossary names. Add new characters/terms to glossary.

**Step 4**: Scan the translated text for traditional Chinese characters. Replace any found with simplified equivalents.

**Step 5**: Save to `workspace/translated/chapter_NNNN.md`

**Step 6**: Update `workspace/summary.json`:
- `last_chapter`: N
- `plot_summary`: Condense earlier events, keep under 500 words total
- `current_situation`: Where things stand at chapter end
- `pending_threads`: Unresolved plot threads

**Step 7**: Update `workspace/glossary.json` with any new names/places/terms

**Step 8**: Report: "Chapter N/M done."

Do not ask to continue. Just proceed to the next chapter.

## Phase 3: Non-Spoiler Summary

After all chapters are translated, read `workspace/summary.json` and generate a **non-spoiler summary** of the book. This goes at the front of the EPUB.

Rules for the summary:
- Describe the setup, setting, and main character(s) — what the reader needs to know going in
- Hint at themes and the kind of story this is (mystery, romance, dystopian, literary fiction, etc.)
- Reveal ONLY what would appear on the back cover or dust jacket of a published book
- Never spoil major plot twists, the ending, or revelations from the second half of the book
- Write in Chinese (简体中文), 150-300 characters
- Title it "内容简介"

Save to `workspace/summary_cn.txt`.

## Phase 4: Build EPUB

```bash
python scripts/build_epub.py workspace/
```

The script produces `workspace/<ChineseTitle>.epub` with:

### EPUB metadata
- **Title**: "English Title —— 中文书名" (bilingual, with em-dash separator)
- **Author**: Original author name (English)
- **Translator**: "Claude (AI Literary Translator)"
- **Language**: zh-CN

### EPUB contents (in order)
1. **Cover page**: `workspace/cover.jpg` as the epub cover image
2. **Title page**: Bilingual title + author + translator credit
3. **内容简介**: The non-spoiler Chinese summary
4. **Chapters**: Each translated chapter as a separate internal section
5. **翻译术语表**: The complete glossary appendix

### Dependencies for EPUB building
```bash
pip install ebooklib beautifulsoup4 lxml pymupdf Pillow requests
```

The script uses `ebooklib` to create a valid EPUB 3.0 file with proper NCX and NAV tables of content.

## Workspace structure

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
└── <BookTitle>.epub        ← Final deliverable
```

## Quick reference: script commands

```bash
# Extract text from EPUB
python scripts/extract_epub.py "<book.epub>" workspace/extracted/

# Extract text from PDF
python scripts/extract_pdf.py "<book.pdf>" workspace/extracted/

# Fetch or generate cover image
python scripts/fetch_cover.py "<Book Title>" "workspace/cover.jpg"

# Build final EPUB
python scripts/build_epub.py workspace/

# Install all dependencies
pip install ebooklib beautifulsoup4 lxml pymupdf Pillow requests
```
