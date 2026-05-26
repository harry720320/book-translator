---
name: book-translator
description: Translate entire English books into fluent, literary Chinese. Supports TXT, EPUB, and PDF input. Use when the user wants to translate a book, novel, or long English text into Chinese. Triggers on "translate this book", "translate to Chinese", "翻译这本书", "英译中", "book translation", "translate this novel", "turn this into Chinese", or whenever someone provides a book file (.txt, .epub, .pdf) and asks for Chinese translation. Also use when the user wants to translate long-form English content chapter by chapter with consistent terminology.
---

# Book Translator

Translate entire English books into natural, literary Chinese — the kind that reads as if it were originally written in Chinese.

## High-Level Flow

```
Input file (.txt/.epub/.pdf)
    → Extract text + detect chapters (scripts/)
    → Translate chapter by chapter with running context
    → Assemble final output (.md)
```

## Phase 1: Extraction

### TXT files

Read directly. Split into chapters by looking for patterns like `Chapter 1`, `CHAPTER ONE`, `1.`, or blank-line-separated sections. If no chapter markers exist, split every ~3000 words at paragraph boundaries.

Save chapters to `workspace/extracted/chapters/chapter_0001.txt`, etc.

### EPUB files

Run the bundled extraction script:

```bash
python scripts/extract_epub.py <book.epub> workspace/extracted/
```

This produces:
- `workspace/extracted/chapters/chapter_0001.txt` ... — one file per chapter
- `workspace/extracted/metadata.json` — chapter titles, word counts, total stats

The script reads the EPUB's TOC/spine and falls back to HTML parsing if needed.

### PDF files

```bash
python scripts/extract_pdf.py <book.pdf> workspace/extracted/
```

Same output structure. The script uses pymupdf for text extraction and detects chapter boundaries from headings, font sizes, or page markers.

### Required dependencies

If a script fails with missing imports, install what's needed:

```bash
pip install ebooklib beautifulsoup4 lxml pymupdf
```

### After extraction

Read `workspace/extracted/metadata.json` and report to the user:
- Total chapters found
- Total word count
- Chapter titles (first 10, then "...")

Ask the user to confirm chapter detection looks correct before proceeding. If chapters are wrong (merged, split incorrectly, missing), adjust manually and update metadata.json.

## Phase 2: Translation Loop

This is the core of the skill. Translate one chapter at a time, maintaining a **running summary** that provides continuity across chapters.

### State files (in `workspace/`)

| File | Purpose |
|------|---------|
| `summary.json` | Running context: characters, places, terms, plot summary |
| `glossary.json` | Master name/term translation dictionary |
| `translated/chapter_0001.md` | Each translated chapter |
| `output.md` | Final assembled book (built incrementally) |

### Initialize state

Before translating the first chapter, create `workspace/glossary.json`:

```json
{
  "characters": {},
  "places": {},
  "terms": {},
  "notes": []
}
```

Create `workspace/summary.json`:

```json
{
  "last_chapter": 0,
  "plot_summary": "",
  "current_situation": "",
  "pending_threads": []
}
```

### Chapter translation loop

For each chapter `N` from 1 to total:

**Step 1 — Read the chapter:**
Read `workspace/extracted/chapters/chapter_NNNN.txt`.

**Step 2 — Prepare context:**
Read `workspace/summary.json` and `workspace/glossary.json`. This is the context for the current chapter.

**Step 3 — Translate:**
Translate the chapter following these rules (see `references/translation-style.md` for full guidelines):

- Produce literary, idiomatic Chinese — not translationese
- Use the glossary for all names and terms; add new entries as they appear
- Match the original tone and register
- Break long English sentences into natural Chinese rhythm
- Handle idioms and cultural references naturally

Output format for each chapter:

```markdown
## Chapter N: [Chapter Title in Chinese]

[Translated text with paragraph breaks matching the original flow]
```

Save to `workspace/translated/chapter_NNNN.md`.

Append it to `workspace/output.md` (with a blank line between chapters).

**Step 4 — Update running summary:**
After translating, update `workspace/summary.json`:

- `last_chapter`: N
- `plot_summary`: Concise summary of the story so far (expand incrementally, keep under 500 words by condensing earlier events)
- `current_situation`: Where things stand at the end of this chapter (who is where, what just happened)
- `pending_threads`: Unresolved plot threads the translator should remember

**Step 5 — Update glossary:**
Add any new characters, places, or terms discovered in this chapter to `workspace/glossary.json`. Record both the English original and the Chinese translation used.

**Step 6 — Report progress:**
Tell the user: "Translated Chapter N: [title] (X words → Y Chinese characters). Total progress: N/M chapters."

### Pausing and resuming

If the session ends mid-book, the next session can pick up by reading `workspace/summary.json` and `workspace/glossary.json`, then continuing from `last_chapter + 1`.

## Phase 3: Final Assembly

After all chapters are translated:

1. Verify `workspace/output.md` has all chapters in order
2. Append a **Translation Glossary** section at the end listing all characters, places, and terms with their English→Chinese mappings
3. Report final stats: total Chinese characters, chapters, any notes on difficult passages

The final deliverable is `workspace/output.md` — a single Markdown file containing the complete translated book.

## Special cases

### Very short books (< 3 chapters / < 5000 words)

Skip the chapter loop and translate in one pass. Still build glossary for consistency.

### Bilingual output

If the user wants bilingual (English + Chinese), output each paragraph as:

```
> English original paragraph

Chinese translation paragraph
```

### Quality review

If the user asks to review a specific chapter, re-read the original chapter text and the translation, and check against the guidelines in `references/translation-style.md`. Focus on: name consistency, natural Chinese flow, and tone matching.

## Workspace structure

```
workspace/
├── extracted/
│   ├── metadata.json
│   └── chapters/
│       ├── chapter_0001.txt
│       ├── chapter_0002.txt
│       └── ...
├── translated/
│   ├── chapter_0001.md
│   ├── chapter_0002.md
│   └── ...
├── summary.json
├── glossary.json
└── output.md
```
